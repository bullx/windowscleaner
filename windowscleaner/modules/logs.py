"""Windows / app log files and diagnostic dumps."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item, filter_items
from windowscleaner.utils.fs import clear_directory_contents, delete_path, merge_results
from windowscleaner.utils.size import path_size


def _targets() -> list[tuple[str, str, Path, str]]:
    """(id, label, path, mode) mode: clear | delete_files | glob"""
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))

    return [
        ("cbs_logs", "Component Based Servicing logs", windir / "Logs" / "CBS", "clear"),
        ("dism_logs", "DISM logs", windir / "Logs" / "DISM", "clear"),
        ("wu_logs", "Windows Update logs", windir / "Logs" / "WindowsUpdate", "clear"),
        ("panther", "Setup Panther logs", windir / "Panther", "clear"),
        ("minidump", "Kernel minidumps", windir / "Minidump", "clear"),
        (
            "memory_dmp",
            "Memory.dmp (full crash dump)",
            windir / "MEMORY.DMP",
            "delete_file",
        ),
        (
            "wer_programdata",
            "Windows Error Reporting (system)",
            programdata / "Microsoft" / "Windows" / "WER",
            "clear",
        ),
        (
            "diagtrack_etl",
            "Diagnostics / telemetry ETL leftovers",
            programdata / "Microsoft" / "Diagnosis",
            "clear",
        ),
        ("inetpub_logs", "IIS logs (if present)", Path(r"C:\inetpub\logs"), "clear"),
    ]


class LogsModule(CleanModule):
    id = "logs"
    label = "Logs & Crash Dumps"
    description = (
        "CBS/DISM/Windows Update logs, minidumps, MEMORY.DMP, "
        "Windows Error Reporting archives, and Diagnosis folder leftovers."
    )
    risk = Risk.SAFE
    requires_admin = True
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, label, path, _mode in _targets():
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
                    requires_admin=True,
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
        from windowscleaner.utils.admin import is_admin

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
        admin = is_admin()
        for item_id, label, path, mode in _targets():
            if not allow_item(item_id, only_ids):
                continue
            try:
                if not path.exists():
                    continue
            except OSError:
                continue
            item = CleanItem(
                id=item_id,
                label=label,
                detail=str(path),
                requires_admin=True,
            )
            result.items.append(item)
            if not admin:
                item.detail = "Needs Administrator - not cleaned (will show again on Scan)"
                result.errors.append(f"{item_id}: needs Administrator")
                continue
            if progress:
                progress(f"Cleaning {label}")
            if mode == "delete_file":
                results.append(delete_path(path, dry_run=False))
            else:
                results.append(clear_directory_contents(path, dry_run=False))
            result.actions.append(f"Cleaned {label}")

        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
            result.errors.extend(merged.errors)
        return result
