"""Temporary files and Windows temp directories."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk
from windowscleaner.utils.admin import is_admin
from windowscleaner.utils.fs import clear_directory_contents, merge_results
from windowscleaner.utils.size import path_size


def _temp_targets() -> list[tuple[str, Path, bool]]:
    """(id, path, requires_admin)"""
    user_temp = Path(tempfile.gettempdir()).resolve()
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))

    candidates = [
        ("user_temp", user_temp, False),
        ("windows_temp", (windir / "Temp").resolve(), True),
        ("recent", Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Recent", False),
    ]

    tmp_env = Path(os.environ.get("TMP", user_temp))
    try:
        if tmp_env.resolve() != user_temp:
            candidates.append(("tmp_env", tmp_env, False))
    except OSError:
        pass

    if local:
        candidates.append(("iedownload", local / r"Microsoft\Windows\INetCache", False))
        candidates.append(("wer_user", local / r"Microsoft\Windows\WER", False))
        candidates.append(("minidump_user", local / "CrashDumps", False))

    seen: set[str] = set()
    targets: list[tuple[str, Path, bool]] = []
    for item_id, path, needs_admin in candidates:
        if not str(path):
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        targets.append((item_id, path, needs_admin))
    return targets


class TempFilesModule(CleanModule):
    id = "temp_files"
    label = "Temporary Files"
    description = (
        "User and system TEMP folders, recent-docs shortcuts, "
        "Internet cache leftovers, and user crash dumps."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, path, needs_admin in _temp_targets():
            if progress:
                progress(f"Scanning {path}")
            try:
                exists = path.exists()
            except OSError:
                exists = False
            size = path_size(path) if exists else 0
            if size <= 0 and not exists:
                continue
            result.items.append(
                CleanItem(
                    id=item_id,
                    label=path.name or str(path),
                    detail=str(path),
                    bytes_estimate=size,
                    requires_admin=needs_admin,
                )
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        # Dry-run: one size walk via scan. Real clean: delete walk only (no double scan).
        if dry_run:
            result = self.scan(progress)
            result.dry_run = True
            for item in result.items:
                result.bytes_freed += item.bytes_estimate
                result.actions.append(f"Would free from {item.detail}")
            return result

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=False)
        admin = is_admin()
        results = []
        for item_id, path, needs_admin in _temp_targets():
            try:
                if not path.exists():
                    continue
            except OSError:
                continue
            item = CleanItem(
                id=item_id,
                label=path.name or str(path),
                detail=str(path),
                requires_admin=needs_admin,
            )
            result.items.append(item)
            if needs_admin and not admin:
                item.detail = "Needs Administrator - not cleaned (will show again on Scan)"
                result.errors.append(f"{item_id}: needs Administrator")
                continue
            if progress:
                progress(f"Clearing {path}")
            r = clear_directory_contents(path, dry_run=False)
            results.append(r)
            result.actions.append(f"Freed from {path}")
            if r.errors:
                result.errors.extend(r.errors)

        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
        return result
