"""System Restore checkpoint helper (ShutUp10 / community safety practice)."""

from __future__ import annotations

import subprocess


def create_restore_point(description: str = "Windows Cleaner checkpoint") -> tuple[bool, str]:
    """Create a System Restore point. Returns (ok, message)."""
    safe_desc = description.replace("'", "").replace('"', "")
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"Checkpoint-Computer -Description '{safe_desc}' -RestorePointType MODIFY_SETTINGS; "
        "'OK'"
    )
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode == 0 and "OK" in (proc.stdout or "").upper():
        return True, "System Restore point created."
    # Common: restore points limited to one per 24h unless registry override
    if "0x80070422" in out or "disabled" in out.lower():
        return False, "System Restore appears disabled."
    if "2147942487" in out or "already been created" in out.lower() or "0x8004230f" in out.lower():
        return False, "A restore point was recently created (Windows rate-limit)."
    return False, out.splitlines()[-1] if out else f"Restore point failed (exit {proc.returncode})."
