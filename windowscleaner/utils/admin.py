"""Admin elevation helpers."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or "\t" in arg) else arg


def relaunch_as_admin() -> None:
    """Relaunch the current process with a UAC elevation prompt."""
    # PyInstaller / frozen EXE: re-run the same binary elevated.
    if getattr(sys, "frozen", False):
        params = " ".join(_quote(a) for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        return

    argv0 = Path(sys.argv[0]).name.lower()
    extra = [a for a in sys.argv[1:] if a]

    if argv0 == "main.py":
        params = " ".join([_quote(sys.argv[0]), *(_quote(a) for a in extra)])
    elif "windowscleaner" in Path(sys.argv[0]).as_posix().lower() or argv0 == "__main__.py":
        params = " ".join(["-m", "windowscleaner", *(_quote(a) for a in extra)])
    else:
        params = " ".join(_quote(a) for a in sys.argv)

    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        None,
        1,
    )
