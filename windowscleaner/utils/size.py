"""Human-readable size formatting and disk measurement."""

from __future__ import annotations

import os
import stat
from pathlib import Path

# Soft cap so a pathological TEMP tree cannot freeze the UI for minutes.
_MAX_FILES_DEFAULT = 80_000


def format_bytes(n: int | float) -> str:
    n = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def path_size(path: Path, *, max_files: int = _MAX_FILES_DEFAULT) -> int:
    """Return total size of a file or directory tree. Missing paths -> 0.

    Uses os.scandir (cheaper than Path.rglob on large trees) and skips
    symlinks so we do not recurse into junctions forever.
    """
    try:
        st = os.lstat(path)
    except (OSError, PermissionError):
        return 0

    if stat.S_ISLNK(st.st_mode):
        return 0
    if stat.S_ISREG(st.st_mode):
        return int(st.st_size)
    if not stat.S_ISDIR(st.st_mode):
        return 0

    total = 0
    files_seen = 0
    stack = [os.fspath(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            files_seen += 1
                            if files_seen >= max_files:
                                return total
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            continue
    return total
