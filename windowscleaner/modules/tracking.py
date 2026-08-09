"""Clear local tracking / activity / advertising residue."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item, filter_items
from windowscleaner.utils.fs import clear_directory_contents, delete_path, merge_results
from windowscleaner.utils.size import path_size


def _targets() -> list[tuple[str, str, Path]]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))

    return [
        ("activity_history", "Timeline / Activity History DB", local / "ConnectedDevicesPlatform"),
        (
            "search_cortana",
            "Search / Cortana local state",
            local / "Packages" / "Microsoft.Windows.Search_cw5n1h2txyewy",
        ),
        (
            "cortana_pkg",
            "Cortana package data",
            local / "Packages" / "Microsoft.549981C3F5F10_8wekyb3d8bbwe",
        ),
        (
            "notifications",
            "Notification history",
            local / "Microsoft" / "Windows" / "Notifications",
        ),
        (
            "clipboard",
            "Clipboard history",
            local / "Microsoft" / "Windows" / "Clipboard",
        ),
        (
            "cdm",
            "Content Delivery Manager (Start suggestions)",
            local / "Packages" / "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy",
        ),
        (
            "onedrive_logs",
            "OneDrive logs",
            local / "Microsoft" / "OneDrive" / "logs",
        ),
        (
            "speech",
            "Speech services cache",
            local / "Microsoft" / "SpeechServices",
        ),
        (
            "diag_programdata",
            "Shared diagnostics / telemetry stage",
            programdata / "Microsoft" / "Diagnosis",
        ),
    ]


class TrackingModule(CleanModule):
    id = "tracking"
    label = "Tracking & Activity Data"
    description = (
        "Timeline/Activity History databases, Search/Cortana leftovers, "
        "notification & clipboard history, Content Delivery suggestion caches, "
        "and shared diagnostic staging folders."
    )
    risk = Risk.MODERATE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, label, path in _targets():
            if progress:
                progress(f"Scanning {label}")
            size = path_size(path)
            if size <= 0:
                continue
            result.items.append(
                CleanItem(
                    id=item_id,
                    label=label,
                    detail=str(path),
                    bytes_estimate=size,
                    requires_admin=(item_id == "diag_programdata"),
                )
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

        from windowscleaner.utils.admin import is_admin

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=False)
        results = []
        admin = is_admin()
        clear_ids = {
            "activity_history",
            "notifications",
            "clipboard",
            "onedrive_logs",
            "speech",
            "diag_programdata",
        }
        package_ids = {"search_cortana", "cortana_pkg", "cdm"}

        for item_id, label, path in _targets():
            if not allow_item(item_id, only_ids):
                continue
            try:
                if not path.exists():
                    continue
            except OSError:
                continue
            needs_admin = item_id == "diag_programdata"
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

            if item_id in clear_ids:
                results.append(clear_directory_contents(path, dry_run=False))
            elif item_id in package_ids:
                for sub in ("LocalCache", "TempState", "AC"):
                    subpath = path / sub
                    if subpath.is_dir():
                        results.append(clear_directory_contents(subpath, dry_run=False))
                local_state = path / "LocalState"
                if local_state.is_dir():
                    # Shallow only — avoid deep rglob across huge package trees
                    for pattern in ("*.db", "*.db-wal", "*.db-shm", "*.log", "*.etl"):
                        for f in local_state.glob(pattern):
                            results.append(delete_path(f, dry_run=False))
                        for f in local_state.glob("*/" + pattern):
                            results.append(delete_path(f, dry_run=False))
            else:
                results.append(clear_directory_contents(path, dry_run=False))

            result.actions.append(f"Cleaned {label}")

        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
            result.errors.extend(merged.errors)
        return result
