"""Recycle Bin emptier."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk


SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004


class RecycleBinModule(CleanModule):
    id = "recycle_bin"
    label = "Recycle Bin"
    description = "Permanently empties the Recycle Bin for all drives."
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        if progress:
            progress("Querying Recycle Bin…")
        size = _recycle_bin_size()
        if size > 0:
            result.items.append(
                CleanItem(
                    id="recycle_bin",
                    label="Recycle Bin",
                    detail="All drives",
                    bytes_estimate=size,
                )
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        result = self.scan(progress)
        result.dry_run = dry_run
        if not result.items:
            return result
        size = result.items[0].bytes_estimate
        if dry_run:
            result.bytes_freed = size
            result.actions.append(f"Would empty Recycle Bin (~{size} bytes)")
            return result
        if progress:
            progress("Emptying Recycle Bin…")
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        # S_OK = 0; E_UNEXPECTED (0x8000FFFF) sometimes if already empty
        if hr in (0, 0x8000FFFF, -2147418113):
            result.bytes_freed = size
            result.actions.append("Emptied Recycle Bin")
        else:
            result.errors.append(f"SHEmptyRecycleBin failed: HRESULT 0x{hr & 0xFFFFFFFF:08X}")
        return result


def _recycle_bin_size() -> int:
    """Best-effort size via SHQueryRecycleBin."""

    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("i64Size", ctypes.c_int64),
            ("i64NumItems", ctypes.c_int64),
        ]

    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
    # NULL pszRootPath → all drives
    hr = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    if hr != 0:
        return 0
    return max(0, int(info.i64Size))
