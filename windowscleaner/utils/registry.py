"""Thin winreg wrappers for privacy / telemetry hardening."""

from __future__ import annotations

import winreg
from dataclasses import dataclass
from typing import Any


HIVE_MAP = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKU": winreg.HKEY_USERS,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
}

# Always use the 64-bit view so reads match writes (Python may be 32-bit).
_READ = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
_WRITE = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY


@dataclass
class RegChange:
    hive: str
    path: str
    name: str
    value: Any
    value_type: int
    previous: Any | None = None
    created: bool = False
    ok: bool = False
    error: str | None = None


def get_value(hive: str, path: str, name: str, default=None):
    try:
        with winreg.OpenKey(HIVE_MAP[hive], path, 0, _READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        # Fallback without WOW64 flag (some HKCU paths)
        try:
            with winreg.OpenKey(HIVE_MAP[hive], path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, name)
                return value
        except OSError:
            return default


def values_match(current: Any, desired: Any) -> bool:
    """True when the setting is already at the desired value."""
    if current is None:
        return False
    try:
        return int(current) == int(desired)
    except (TypeError, ValueError):
        return current == desired


def set_dword(hive: str, path: str, name: str, value: int, *, dry_run: bool = False) -> RegChange:
    return _set(hive, path, name, int(value), winreg.REG_DWORD, dry_run=dry_run)


def set_sz(hive: str, path: str, name: str, value: str, *, dry_run: bool = False) -> RegChange:
    return _set(hive, path, name, str(value), winreg.REG_SZ, dry_run=dry_run)


def _set(
    hive: str,
    path: str,
    name: str,
    value: Any,
    value_type: int,
    *,
    dry_run: bool,
) -> RegChange:
    change = RegChange(hive=hive, path=path, name=name, value=value, value_type=value_type)
    change.previous = get_value(hive, path, name)

    if dry_run:
        change.ok = True
        return change

    # Prefer 64-bit view; fall back for odd HKCU ACLs.
    attempts = [_WRITE, winreg.KEY_READ | winreg.KEY_WRITE]
    last_error: str | None = None

    for access in attempts:
        try:
            key = winreg.CreateKeyEx(HIVE_MAP[hive], path, 0, access)
            change.created = True
            with key:
                winreg.SetValueEx(key, name, 0, value_type, value)
            # Verify write actually stuck (same view as get_value)
            written = get_value(hive, path, name)
            if values_match(written, value):
                change.ok = True
                return change
            last_error = f"write did not stick (read back {written!r})"
        except OSError as e:
            last_error = str(e)
            continue

    change.error = last_error or "failed to write registry value"
    change.ok = False
    return change
