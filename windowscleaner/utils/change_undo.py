"""Remember Run-key values and service start types so they can be restored."""

from __future__ import annotations

import json
import os
import time
import winreg
from pathlib import Path
from typing import Any

from windowscleaner.utils.proc import run_hidden

_HIVES = {
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
}


def undo_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WindowsCleaner"
    base.mkdir(parents=True, exist_ok=True)
    return base / "change_undo.json"


def load_undo() -> dict[str, Any]:
    path = undo_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "when": 0, "entries": []}


def save_undo(data: dict[str, Any]) -> None:
    try:
        undo_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def normalize_start(text: str | None) -> str | None:
    """Map `sc qc` START_TYPE text to an `sc config start=` token."""
    if not text:
        return None
    raw = text.strip().lower()
    if raw in {"auto", "demand", "disabled", "delayed-auto", "boot", "system"}:
        return raw
    upper = text.upper()
    if "DELAYED" in upper:
        return "delayed-auto"
    if "AUTO" in upper:
        return "auto"
    if "DEMAND" in upper:
        return "demand"
    if "DISABLED" in upper:
        return "disabled"
    if "BOOT" in upper:
        return "boot"
    if "SYSTEM" in upper:
        return "system"
    return None


def _remember(entry: dict[str, Any]) -> None:
    """Keep the first value recorded for an id (the pre-tool value)."""
    data = load_undo()
    entries: list[dict[str, Any]] = list(data.get("entries") or [])
    if any(e.get("id") == entry["id"] for e in entries):
        return
    entries.append(entry)
    data["entries"] = entries[-400:]
    data["when"] = time.time()
    data["version"] = 1
    save_undo(data)


def remember_run(
    *,
    hive: str,
    path: str,
    name: str,
    value: Any,
    reg_type: int,
) -> None:
    _remember(
        {
            "kind": "run",
            "id": f"run:{hive}:{name}",
            "label": f"{hive} Run: {name}",
            "hive": hive,
            "path": path,
            "name": name,
            "value": value if isinstance(value, (str, int)) else str(value),
            "reg_type": int(reg_type),
            "when": time.time(),
        }
    )


def remember_service(*, name: str, start_text: str | None) -> None:
    token = normalize_start(start_text)
    if not token:
        return
    _remember(
        {
            "kind": "service",
            "id": f"svc:{name}",
            "label": f"Service start: {name}",
            "name": name,
            "start": token,
            "when": time.time(),
        }
    )


def undo_all(*, dry_run: bool = False) -> tuple[int, int, list[str]]:
    """Restore recorded Run values and service start types."""
    data = load_undo()
    entries = list(data.get("entries") or [])
    if not entries:
        return 0, 0, ["No startup or service undo history found."]

    ok = 0
    failed = 0
    messages: list[str] = []
    remaining: list[dict[str, Any]] = []

    for entry in reversed(entries):
        kind = entry.get("kind")
        label = str(entry.get("label") or entry.get("id") or "")
        if kind == "run":
            success, msg, keep = _restore_run(entry, dry_run=dry_run)
        elif kind == "service":
            success, msg, keep = _restore_service(entry, dry_run=dry_run)
        else:
            success, msg, keep = False, f"{label}: unknown undo kind", True
        messages.append(msg)
        if success:
            ok += 1
        else:
            failed += 1
        if keep:
            remaining.append(entry)

    if not dry_run:
        data["entries"] = list(reversed(remaining))
        data["when"] = time.time()
        save_undo(data)
    return ok, failed, messages


def _restore_run(entry: dict[str, Any], *, dry_run: bool) -> tuple[bool, str, bool]:
    hive_name = str(entry.get("hive") or "")
    path = str(entry.get("path") or "")
    name = str(entry.get("name") or "")
    value = entry.get("value")
    reg_type = int(entry.get("reg_type") or winreg.REG_SZ)
    label = str(entry.get("label") or name)
    hive = _HIVES.get(hive_name)
    if hive is None or not path or not name or value is None:
        return False, f"{label}: incomplete record", True
    if dry_run:
        return True, f"Would restore {label}", True
    access = winreg.KEY_SET_VALUE | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.CreateKeyEx(hive, path, 0, access) as key:
            winreg.SetValueEx(key, name, 0, reg_type, value)
        return True, f"Restored {label}", False
    except OSError as exc:
        return False, f"{label}: {exc}", True


def _restore_service(entry: dict[str, Any], *, dry_run: bool) -> tuple[bool, str, bool]:
    name = str(entry.get("name") or "")
    start = normalize_start(str(entry.get("start") or ""))
    label = str(entry.get("label") or name)
    if not name or not start:
        return False, f"{label}: incomplete record", True
    if dry_run:
        return True, f"Would set {name} start= {start}", True
    proc = run_hidden(["sc", "config", name, "start=", start])
    if proc.returncode == 0:
        return True, f"Restored {name} start= {start}", False
    err = (proc.stderr or proc.stdout or "failed").strip()
    return False, f"{label}: {err}", True
