"""Subprocess helper that does not flash a console window."""

from __future__ import annotations

import subprocess


def run_hidden(
    cmd: list[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
        creationflags=flags,
    )
