"""Persist previous privacy registry values so users can undo a Clean."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from windowscleaner.utils.registry import get_value, set_dword, values_match


def undo_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WindowsCleaner"
    base.mkdir(parents=True, exist_ok=True)
    return base / "privacy_undo.json"


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


def record_change(
    *,
    setting_id: str,
    label: str,
    hive: str,
    path: str,
    name: str,
    previous: Any,
    applied: int,
) -> None:
    """Append one successful privacy write (keeps last ~200 entries)."""
    data = load_undo()
    entries: list[dict[str, Any]] = list(data.get("entries") or [])
    # Drop older duplicate for same setting so undo restores the pre-tool value once
    entries = [e for e in entries if e.get("id") != setting_id]
    entries.append(
        {
            "id": setting_id,
            "label": label,
            "hive": hive,
            "path": path,
            "name": name,
            "previous": previous,
            "applied": applied,
            "when": time.time(),
        }
    )
    data["entries"] = entries[-200:]
    data["when"] = time.time()
    data["version"] = 1
    save_undo(data)


def undo_all(*, dry_run: bool = False) -> tuple[int, int, list[str]]:
    """
    Restore recorded previous values.
    Returns (restored_ok, skipped_or_failed, messages).
    """
    data = load_undo()
    entries = list(data.get("entries") or [])
    if not entries:
        return 0, 0, ["No privacy undo history found."]

    ok = 0
    failed = 0
    messages: list[str] = []
    remaining: list[dict[str, Any]] = []

    for entry in reversed(entries):  # newest first
        sid = str(entry.get("id") or "")
        hive = str(entry.get("hive") or "")
        path = str(entry.get("path") or "")
        name = str(entry.get("name") or "")
        previous = entry.get("previous")
        label = str(entry.get("label") or sid)

        if previous is None:
            messages.append(f"{label}: no previous value recorded (was missing) — skipped")
            failed += 1
            continue

        try:
            desired = int(previous)
        except (TypeError, ValueError):
            messages.append(f"{label}: previous value not a DWORD — skipped")
            failed += 1
            remaining.append(entry)
            continue

        current = get_value(hive, path, name)
        if values_match(current, desired):
            messages.append(f"{label}: already at previous value")
            ok += 1
            continue

        if dry_run:
            messages.append(f"Would restore {label}: {current!r} -> {desired}")
            ok += 1
            remaining.append(entry)
            continue

        change = set_dword(hive, path, name, desired, dry_run=False)
        if change.ok:
            messages.append(f"Restored {label} to {desired} (was {current!r})")
            ok += 1
        else:
            messages.append(f"{label}: {change.error or 'restore failed'}")
            failed += 1
            remaining.append(entry)

    if not dry_run:
        # Keep only failed entries for retry
        data["entries"] = list(reversed(remaining))
        data["when"] = time.time()
        save_undo(data)

    return ok, failed, messages


def clear_undo() -> None:
    save_undo({"version": 1, "when": 0, "entries": []})
