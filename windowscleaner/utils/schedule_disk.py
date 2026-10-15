"""Weekly Task Scheduler entry for a Free disk clean. Not a resident optimizer."""

from __future__ import annotations

import sys

from windowscleaner.utils.proc import run_hidden

TASK_NAME = "WindowsCleaner-FreeDisk"


def disk_clean_command() -> str:
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return f'"{exe}" --cli clean --profile disk -y'
    return f'"{sys.executable}" -m windowscleaner --cli clean --profile disk -y'


def install_weekly_disk_task() -> tuple[bool, str]:
    """Create a weekly task that runs `--profile disk`. User can remove it in Task Scheduler."""
    command = disk_clean_command()
    proc = run_hidden(
        [
            "schtasks",
            "/Create",
            "/F",
            "/TN",
            TASK_NAME,
            "/SC",
            "WEEKLY",
            "/D",
            "SUN",
            "/ST",
            "09:00",
            "/RL",
            "LIMITED",
            "/TR",
            command,
        ],
        timeout=60,
    )
    if proc.returncode == 0:
        return True, f"Scheduled {TASK_NAME} every Sunday at 09:00. It runs a Free disk clean."
    err = (proc.stderr or proc.stdout or "schtasks failed").strip()
    return False, err[:500]
