"""Windows Update leftovers, Delivery Optimization, thumbnail & icon caches."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk
from windowscleaner.utils.fs import clear_directory_contents, delete_path, merge_results
from windowscleaner.utils.size import path_size


def _targets() -> list[tuple[str, str, Path, bool]]:
    """(id, label, path, requires_admin)"""
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))

    return [
        (
            "wu_download",
            "Windows Update download cache",
            windir / r"SoftwareDistribution\Download",
            True,
        ),
        (
            "delivery_opt",
            "Delivery Optimization cache",
            windir / "SoftwareDistribution" / "DeliveryOptimization",
            True,
        ),
        (
            "delivery_opt_alt",
            "Delivery Optimization files",
            Path(r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local"
                 r"\Microsoft\Windows\DeliveryOptimization\Cache"),
            True,
        ),
        (
            "thumbcache",
            "Explorer thumbnail cache",
            local / r"Microsoft\Windows\Explorer",
            False,
        ),
        (
            "font_cache",
            "Font cache (service files)",
            windir / "ServiceProfiles" / "LocalService" / "AppData" / "Local" / "FontCache",
            True,
        ),
        (
            "prefetch",
            "Prefetch (rarely needed; may slow next cold boots briefly)",
            windir / "Prefetch",
            True,
        ),
        (
            "installer_cache_partial",
            "Windows Installer patch cache leftovers",
            windir / "Installer" / "$PatchCache$",
            True,
        ),
        (
            "do_programdata",
            "Delivery Optimization ProgramData",
            programdata / "Microsoft" / "Windows" / "DeliveryOptimization",
            True,
        ),
        (
            "webcache",
            "Windows WebCache (Explorer/Edge leftovers)",
            local / r"Microsoft\Windows\WebCache",
            False,
        ),
        (
            "windows_old",
            "Windows.old (previous Windows installation — large, irreversible)",
            Path(r"C:\Windows.old"),
            True,
        ),
    ]


class CachesModule(CleanModule):
    id = "caches"
    label = "System & Update Caches"
    description = (
        "Windows Update download cache, Delivery Optimization P2P cache, "
        "Explorer thumbnails, optional Prefetch, and Windows.old if present."
    )
    risk = Risk.MODERATE
    # Some targets (thumbnails / WebCache) work without elevation; others need Admin.
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, label, path, needs_admin in _targets():
            if progress:
                progress(f"Scanning {label}")
            # Thumbnail cache: only db files
            if item_id == "thumbcache":
                size = 0
                if path.exists():
                    for f in path.glob("thumbcache_*.db"):
                        size += path_size(f)
                    for f in path.glob("iconcache_*.db"):
                        size += path_size(f)
            else:
                size = path_size(path)
            if size <= 0:
                continue
            result.items.append(
                CleanItem(
                    id=item_id,
                    label=label,
                    detail=str(path),
                    bytes_estimate=size,
                    requires_admin=needs_admin,
                )
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        if dry_run:
            result = self.scan(progress)
            result.dry_run = True
            result.bytes_freed = result.bytes_estimate
            for item in result.items:
                result.actions.append(f"Would clean {item.label}")
            return result

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=False)
        results = []
        admin = is_admin()
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        for item_id, label, path, needs_admin in _targets():
            try:
                exists = path.exists()
            except OSError:
                exists = False
            if not exists:
                continue
            item = CleanItem(
                id=item_id,
                label=label,
                detail=str(path),
                requires_admin=needs_admin,
            )
            result.items.append(item)
            if needs_admin and not admin:
                item.detail = "Needs Administrator - not cleaned (will show again on Scan)"
                result.errors.append(f"{item_id}: needs Administrator")
                continue
            if progress:
                progress(f"Cleaning {label}")

            before_errs = len(results)
            if item_id == "thumbcache":
                try:
                    subprocess.run(
                        ["taskkill", "/f", "/im", "explorer.exe"],
                        capture_output=True,
                        check=False,
                        creationflags=flags,
                    )
                except OSError:
                    pass
                for pattern in ("thumbcache_*.db", "iconcache_*.db"):
                    for f in path.glob(pattern):
                        results.append(delete_path(f, dry_run=False))
                try:
                    subprocess.Popen(["explorer.exe"])
                except OSError:
                    pass
            elif item_id == "prefetch":
                for f in path.glob("*.pf"):
                    results.append(delete_path(f, dry_run=False))
            elif item_id == "windows_old":
                # Remove the entire previous-Windows folder (not just contents)
                results.append(delete_path(path, dry_run=False))
            else:
                results.append(clear_directory_contents(path, dry_run=False))

            chunk = results[before_errs:]
            chunk_errs = [e for r in chunk for e in r.errors] if chunk else []
            if chunk_errs:
                result.errors.extend(chunk_errs)
            else:
                result.actions.append(f"Cleaned {label}")

        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
            # errors already collected per chunk; merge may add more
            for e in merged.errors:
                if e not in result.errors:
                    result.errors.append(e)
        return result
