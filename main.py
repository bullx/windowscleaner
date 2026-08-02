#!/usr/bin/env python3
"""Launch Windows Cleaner (GUI by default, CLI with --cli)."""

from __future__ import annotations

import sys


def main() -> int:
    if "--cli" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--cli"]
        from windowscleaner.ui.cli import main as cli_main

        return int(cli_main() or 0)

    from windowscleaner.ui.gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
