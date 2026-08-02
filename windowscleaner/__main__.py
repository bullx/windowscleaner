"""Launch: python -m windowscleaner  (GUI)

Use --cli for the command-line interface:
  python -m windowscleaner --cli scan
"""

from __future__ import annotations

import sys


def _entry() -> int:
    if "--cli" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--cli"]
        from windowscleaner.ui.cli import main as cli_main

        return int(cli_main() or 0)

    from windowscleaner.ui.gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(_entry())
