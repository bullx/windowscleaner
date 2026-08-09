"""Startup programs — scan Run keys / Startup folder; opt-in disable."""

from __future__ import annotations

import os
import winreg
from pathlib import Path

from windowscleaner.modules.base import (
    CleanItem,
    CleanModule,
    ModuleResult,
    OnlyIds,
    ProgressCb,
    Risk,
    filter_items,
)


def _list_run_values(hive: int, path: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.OpenKey(hive, path, 0, access) as key:
            i = 0
            while True:
                try:
                    name, value, _typ = winreg.EnumValue(key, i)
                    i += 1
                except OSError:
                    break
                if name:
                    out.append((str(name), str(value)))
    except OSError:
        # Fallback without WOW64
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _typ = winreg.EnumValue(key, i)
                        i += 1
                    except OSError:
                        break
                    if name:
                        out.append((str(name), str(value)))
        except OSError:
            pass
    return out


def _delete_run_value(hive: int, path: str, name: str) -> tuple[bool, str | None]:
    access = winreg.KEY_SET_VALUE | winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.OpenKey(hive, path, 0, access) as key:
            winreg.DeleteValue(key, name)
        return True, None
    except OSError as e:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                winreg.DeleteValue(key, name)
            return True, None
        except OSError as e2:
            return False, str(e2) or str(e)


def _startup_folder_shortcuts() -> list[tuple[str, Path]]:
    candidates = [
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup",
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        / r"Microsoft\Windows\Start Menu\Programs\Startup",
    ]
    found: list[tuple[str, Path]] = []
    for folder in candidates:
        try:
            if not folder.is_dir():
                continue
            for f in folder.iterdir():
                if f.suffix.lower() in {".lnk", ".url", ".bat", ".cmd", ".exe"}:
                    found.append((f.name, f))
        except OSError:
            continue
    return found


_RUN_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"


class StartupAppsModule(CleanModule):
    id = "startup_apps"
    label = "Startup Programs"
    description = (
        "Lists HKCU/HKLM Run entries and Startup-folder shortcuts that launch at logon. "
        "Clean removes the selected Run value or Startup shortcut (opt-in). "
        "Does not touch services or Task Scheduler — use those tools for service-based agents."
    )
    risk = Risk.MODERATE
    requires_admin = False  # HKCU works without; HKLM / common Startup need Admin per item
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)

        if progress:
            progress("Scanning HKCU Run...")
        for name, value in _list_run_values(winreg.HKEY_CURRENT_USER, _RUN_PATH):
            result.items.append(
                CleanItem(
                    id=f"hkcu_run:{name}",
                    label=f"HKCU Run: {name}",
                    detail=value,
                    bytes_estimate=0,
                    requires_admin=False,
                    effect=f"Removes user Run entry '{name}' so it no longer starts at logon.",
                    repercussions=(
                        "App will not auto-start for this user until re-added. "
                        "You can re-enable from the app's settings or Task Manager Startup."
                    ),
                )
            )

        if progress:
            progress("Scanning HKLM Run...")
        for name, value in _list_run_values(winreg.HKEY_LOCAL_MACHINE, _RUN_PATH):
            result.items.append(
                CleanItem(
                    id=f"hklm_run:{name}",
                    label=f"HKLM Run: {name}",
                    detail=value,
                    bytes_estimate=0,
                    requires_admin=True,
                    effect=f"Removes machine Run entry '{name}' (all users).",
                    repercussions=(
                        "Stops auto-start for all users until reinstalled/re-added. Needs Admin. "
                        "Some OEM agents re-create this via drivers."
                    ),
                )
            )

        if progress:
            progress("Scanning Startup folder...")
        for fname, path in _startup_folder_shortcuts():
            common = "ProgramData" in str(path)
            result.items.append(
                CleanItem(
                    id=f"startup_file:{path}",
                    label=f"Startup folder: {fname}",
                    detail=str(path),
                    bytes_estimate=0,
                    requires_admin=common,
                    effect=f"Deletes Startup shortcut/script: {fname}.",
                    repercussions=(
                        "File removed from Startup folder. Recreate the shortcut to restore. "
                        "Does not uninstall the application."
                    ),
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

        result = self.scan(progress)
        result.items = filter_items(result.items, only_ids)
        result.dry_run = dry_run
        admin = is_admin()

        for item in result.items:
            if progress:
                progress(f"{'Would disable' if dry_run else 'Disabling'} {item.label}")
            if dry_run:
                result.actions.append(f"Would remove {item.id}")
                continue
            if item.requires_admin and not admin:
                item.detail = "Needs Administrator - not removed (will show again on Scan)"
                item.repercussions = "Run Restart as Administrator, then Clean again."
                result.errors.append(f"{item.id}: needs Administrator")
                continue

            if item.id.startswith("hkcu_run:"):
                name = item.id.split(":", 1)[1]
                ok, err = _delete_run_value(winreg.HKEY_CURRENT_USER, _RUN_PATH, name)
                if ok:
                    result.actions.append(f"Removed HKCU Run: {name}")
                else:
                    result.errors.append(f"{item.id}: {err or 'failed'}")
            elif item.id.startswith("hklm_run:"):
                name = item.id.split(":", 1)[1]
                ok, err = _delete_run_value(winreg.HKEY_LOCAL_MACHINE, _RUN_PATH, name)
                if ok:
                    result.actions.append(f"Removed HKLM Run: {name}")
                else:
                    result.errors.append(f"{item.id}: {err or 'failed'}")
            elif item.id.startswith("startup_file:"):
                path = Path(item.id.split(":", 1)[1])
                try:
                    if path.exists():
                        path.unlink()
                    result.actions.append(f"Deleted {path}")
                except OSError as e:
                    result.errors.append(f"{item.id}: {e}")
            else:
                result.errors.append(f"{item.id}: unknown startup item type")

        return result
