"""Browser cache cleanup (Edge / Chrome / Firefox) - community cleaner staple."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item, filter_items
from windowscleaner.utils.fs import clear_directory_contents, merge_results
from windowscleaner.utils.size import path_size


def _targets() -> list[tuple[str, str, Path]]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming = Path(os.environ.get("APPDATA", ""))
    return [
        ("edge_cache", "Edge Cache", local / r"Microsoft\Edge\User Data\Default\Cache"),
        ("edge_code", "Edge Code Cache", local / r"Microsoft\Edge\User Data\Default\Code Cache"),
        ("edge_gpu", "Edge GPU Cache", local / r"Microsoft\Edge\User Data\Default\GPUCache"),
        (
            "edge_gpucache_service",
            "Edge GraphiteDawnCache",
            local / r"Microsoft\Edge\User Data\Default\GraphiteDawnCache",
        ),
        ("chrome_cache", "Chrome Cache", local / r"Google\Chrome\User Data\Default\Cache"),
        ("chrome_code", "Chrome Code Cache", local / r"Google\Chrome\User Data\Default\Code Cache"),
        ("chrome_gpu", "Chrome GPU Cache", local / r"Google\Chrome\User Data\Default\GPUCache"),
        ("firefox_cache", "Firefox cache2", roaming / r"Mozilla\Firefox\Profiles"),
    ]


def _firefox_size(profiles: Path) -> int:
    if not profiles.exists():
        return 0
    total = 0
    for profile in profiles.iterdir():
        if profile.is_dir():
            total += path_size(profile / "cache2")
    return total


class BrowserCachesModule(CleanModule):
    id = "browser_caches"
    label = "Browser Caches"
    description = (
        "Clears Edge / Chrome / Firefox cache folders (not bookmarks or passwords). "
        "Close browsers first for best results. Common target in community cleaners."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, label, path in _targets():
            if progress:
                progress(f"Scanning {label}")
            size = _firefox_size(path) if item_id == "firefox_cache" else path_size(path)
            if size <= 0:
                continue
            result.items.append(
                CleanItem(id=item_id, label=label, detail=str(path), bytes_estimate=size)
            )
        return result

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        if dry_run:
            result = self.scan(progress)
            result.items = filter_items(result.items, only_ids)
            result.dry_run = True
            result.bytes_freed = result.bytes_estimate
            for item in result.items:
                result.actions.append(f"Would clean {item.label}")
            return result

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=False)
        results = []
        for item_id, label, path in _targets():
            if not allow_item(item_id, only_ids):
                continue
            try:
                if not path.exists():
                    continue
            except OSError:
                continue
            result.items.append(CleanItem(id=item_id, label=label, detail=str(path)))
            if progress:
                progress(f"Cleaning {label}")
            if item_id == "firefox_cache":
                for profile in path.iterdir():
                    cache2 = profile / "cache2"
                    if cache2.is_dir():
                        results.append(clear_directory_contents(cache2, dry_run=False))
            else:
                results.append(clear_directory_contents(path, dry_run=False))
            result.actions.append(f"Cleaned {label}")
        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
            result.errors.extend(merged.errors)
        return result
