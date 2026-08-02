"""Safe filesystem helpers for cleanup operations."""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeleteResult:
    deleted_files: int = 0
    deleted_dirs: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _on_rm_error(func, path, _exc_info):
    """Clear read-only bit and retry (common on Windows caches)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def delete_path(path: Path, *, dry_run: bool = False) -> DeleteResult:
    result = DeleteResult()
    path_s = os.fspath(path)
    try:
        st = os.lstat(path_s)
    except FileNotFoundError:
        return result
    except (OSError, PermissionError) as e:
        result.errors.append(f"{path}: {e}")
        return result

    # File or symlink
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        size = int(st.st_size) if stat.S_ISREG(st.st_mode) else 0
        if dry_run:
            result.deleted_files = 1
            result.bytes_freed = size
            return result
        try:
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                try:
                    os.chmod(path_s, stat.S_IWRITE)
                except OSError:
                    pass
                os.unlink(path_s)
                result.deleted_files = 1
                result.bytes_freed = size
        except (OSError, PermissionError) as e:
            result.errors.append(f"{path}: {e}")
        return result

    # Directory tree — single os.walk, minimal Path() overhead
    for root, dirs, files in os.walk(path_s, topdown=False, followlinks=False):
        for name in files:
            fp = os.path.join(root, name)
            size = 0
            try:
                size = os.lstat(fp).st_size
            except OSError:
                pass
            if dry_run:
                result.deleted_files += 1
                result.bytes_freed += size
                continue
            try:
                try:
                    os.chmod(fp, stat.S_IWRITE)
                except OSError:
                    pass
                os.unlink(fp)
                result.deleted_files += 1
                result.bytes_freed += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"{fp}: {e}")

        for name in dirs:
            dp = os.path.join(root, name)
            if dry_run:
                result.deleted_dirs += 1
                continue
            try:
                # rmtree leftover (junctions / stubborn dirs)
                shutil.rmtree(dp, onerror=_on_rm_error)
                result.deleted_dirs += 1
            except (OSError, PermissionError):
                try:
                    os.rmdir(dp)
                    result.deleted_dirs += 1
                except (OSError, PermissionError) as e:
                    result.errors.append(f"{dp}: {e}")

    if not dry_run:
        try:
            if not os.listdir(path_s):
                os.rmdir(path_s)
                result.deleted_dirs += 1
        except (OSError, PermissionError):
            pass
    else:
        result.deleted_dirs += 1

    return result


def clear_directory_contents(path: Path, *, dry_run: bool = False) -> DeleteResult:
    """Delete everything inside a directory but keep the directory itself."""
    result = DeleteResult()
    path_s = os.fspath(path)
    try:
        if not os.path.isdir(path_s):
            return result
    except (OSError, PermissionError) as e:
        result.errors.append(f"{path}: {e}")
        return result

    try:
        with os.scandir(path_s) as it:
            children = [Path(entry.path) for entry in it]
    except (OSError, PermissionError) as e:
        result.errors.append(f"{path}: {e}")
        return result

    for child in children:
        child_result = delete_path(child, dry_run=dry_run)
        result.deleted_files += child_result.deleted_files
        result.deleted_dirs += child_result.deleted_dirs
        result.bytes_freed += child_result.bytes_freed
        result.errors.extend(child_result.errors)

    return result


def merge_results(*results: DeleteResult) -> DeleteResult:
    out = DeleteResult()
    for r in results:
        out.deleted_files += r.deleted_files
        out.deleted_dirs += r.deleted_dirs
        out.bytes_freed += r.bytes_freed
        out.errors.extend(r.errors)
        out.skipped.extend(r.skipped)
    return out
