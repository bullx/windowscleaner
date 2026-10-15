"""Opt-in reclaim of component store, hibernation, shadow-copy cap, and upgrade leftovers.

Dry-run and Scan do not run DISM cleanup or `powercfg -h off`.
`/ResetBase` stays unchecked until the user includes that row.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item
from windowscleaner.utils.admin import is_admin
from windowscleaner.utils.fs import delete_path, merge_results
from windowscleaner.utils.proc import run_hidden
from windowscleaner.utils.size import path_size

_SIZE_RE = re.compile(r"([\d.]+)\s*(TB|GB|MB|KB|B)\b", re.I)
_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}


def system32() -> Path:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    if os.environ.get("PROCESSOR_ARCHITEW6432"):
        return windir / "Sysnative"
    return windir / "System32"


def _drive() -> str:
    drive = os.environ.get("SystemDrive", "C:")
    if not drive.endswith(":"):
        drive += ":"
    return drive


def to_bytes(number: float, unit: str) -> int:
    return int(number * _UNITS[unit.upper()])


def parse_component_store_bytes(text: str) -> int:
    """Sum backup / temporary sizes reported by AnalyzeComponentStore."""
    total = 0
    for line in text.splitlines():
        low = line.lower()
        if not any(token in low for token in ("backup", "cache and temporary", "reclaimable")):
            continue
        match = _SIZE_RE.search(line)
        if match:
            total += to_bytes(float(match.group(1)), match.group(2))
    return total


def cleanup_command(*, resetbase: bool) -> list[str]:
    cmd = [
        str(system32() / "Dism.exe"),
        "/Online",
        "/Cleanup-Image",
        "/StartComponentCleanup",
    ]
    if resetbase:
        cmd.append("/ResetBase")
    return cmd


def analyze_command() -> list[str]:
    return [
        str(system32() / "Dism.exe"),
        "/Online",
        "/Cleanup-Image",
        "/AnalyzeComponentStore",
    ]


def hiberfil_path() -> Path:
    return Path(_drive() + "\\") / "hiberfil.sys"


def upgrade_paths() -> list[Path]:
    root = Path(_drive() + "\\")
    return [root / "$Windows.~BT", root / "$Windows.~WS"]


def parse_shadow_used_and_max(text: str) -> tuple[int, int | None]:
    """Return (used bytes, max bytes). max is None when UNBOUNDED."""
    used = 0
    maximum: int | None = 0
    for line in text.splitlines():
        low = line.lower()
        match = _SIZE_RE.search(line)
        if "used shadow copy storage" in low and match:
            used = to_bytes(float(match.group(1)), match.group(2))
        elif "maximum shadow copy storage" in low:
            if "unbounded" in low:
                maximum = None
            elif match:
                maximum = to_bytes(float(match.group(1)), match.group(2))
    return used, maximum


def shadow_should_shrink(used: int, maximum: int | None) -> bool:
    if used < 100 * 1024 * 1024:
        return False
    if maximum is None:
        return True
    return maximum > max(used * 2, 2 * 1024**3)


def shadow_resize_command(used: int, *, drive: str | None = None) -> list[str]:
    """Shrink the cap. Does not delete every restore point."""
    drive = drive or _drive()
    new_bytes = max(used // 2, 320 * 1024 * 1024)
    megabytes = max(320, new_bytes // (1024 * 1024))
    return [
        "vssadmin",
        "resize",
        "shadowstorage",
        f"/for={drive}",
        f"/on={drive}",
        f"/maxsize={megabytes}MB",
    ]


class SystemReclaimModule(CleanModule):
    id = "system_reclaim"
    label = "System Disk Reclaim"
    description = (
        "Component store cleanup, hibernation file, a smaller System Restore cap, "
        "and leftover Windows upgrade folders. Opt-in and not in Full. "
        "ResetBase stays unchecked: it blocks uninstalling those updates."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        if progress:
            progress("Analyzing component store")
        reclaim = 0
        analyze_detail = "DISM AnalyzeComponentStore"
        try:
            proc = run_hidden(analyze_command(), timeout=300)
            text = (proc.stdout or "") + "\n" + (proc.stderr or "")
            reclaim = parse_component_store_bytes(text)
            if proc.returncode != 0 and reclaim <= 0:
                analyze_detail = "Needs Administrator to measure the component store"
        except OSError as exc:
            analyze_detail = str(exc)
        if reclaim > 0:
            result.items.append(
                CleanItem(
                    id="component_store",
                    label="Component store cleanup",
                    detail=analyze_detail,
                    bytes_estimate=reclaim,
                    requires_admin=True,
                    default_include=True,
                    effect="Removes superseded Windows update files from WinSxS.",
                    repercussions=(
                        "Slow, and needs Administrator. Windows Update keeps working. "
                        "This row does not use /ResetBase."
                    ),
                    risk=self.risk.value,
                )
            )
            result.items.append(
                CleanItem(
                    id="component_store_resetbase",
                    label="Component store cleanup with ResetBase",
                    detail="Unchecked. /ResetBase blocks uninstalling the cleaned updates.",
                    bytes_estimate=reclaim,
                    requires_admin=True,
                    default_include=False,
                    effect="Runs component-store cleanup with /ResetBase.",
                    repercussions=(
                        "Windows can no longer uninstall the updates this removes. "
                        "Leave this unchecked unless you accept that."
                    ),
                    risk=self.risk.value,
                )
            )

        hiber = hiberfil_path()
        try:
            size = path_size(hiber)
        except OSError:
            size = 0
        if size > 0:
            result.items.append(
                CleanItem(
                    id="hiberfil",
                    label="Hibernation file",
                    detail=(
                        f"{hiber} — turning hibernation off also turns off Fast Startup. "
                        "powercfg /a reports whether hibernate is available."
                    ),
                    bytes_estimate=size,
                    requires_admin=True,
                    effect="Turns hibernation off and removes hiberfil.sys.",
                    repercussions=(
                        "Fast Startup turns off too. Sleep still works. "
                        "Turn hibernation back on with powercfg -h on if you need it."
                    ),
                    risk=self.risk.value,
                )
            )

        if progress:
            progress("Reading shadow copy storage")
        try:
            shadow = run_hidden(["vssadmin", "list", "shadowstorage"], timeout=60)
            used, maximum = parse_shadow_used_and_max(shadow.stdout or "")
        except OSError:
            used, maximum = 0, 0
        if shadow_should_shrink(used, maximum):
            cap = "unlimited" if maximum is None else "larger than the copies in use"
            result.items.append(
                CleanItem(
                    id="shadow_copies",
                    label="System Restore storage cap",
                    detail=(
                        f"Used shadow storage can shrink. Current cap is {cap}. "
                        "Older restore points past the new cap may drop. The newest are kept."
                    ),
                    bytes_estimate=used // 2,
                    requires_admin=True,
                    effect="Lowers the shadow-copy cap to about half of what is in use.",
                    repercussions=(
                        "Does not delete every restore point. "
                        "System Restore stays on with a smaller ceiling."
                    ),
                    risk=self.risk.value,
                )
            )

        for path in upgrade_paths():
            try:
                size = path_size(path) if path.exists() else 0
            except OSError:
                size = 0
            if size <= 0:
                continue
            result.items.append(
                CleanItem(
                    id=f"upgrade:{path.name}",
                    label=f"Upgrade leftover {path.name}",
                    detail=str(path),
                    bytes_estimate=size,
                    requires_admin=True,
                    effect="Deletes this leftover Windows setup folder.",
                    repercussions="Same family as Windows.old. The folder is how a failed setup rolls back.",
                    risk=self.risk.value,
                )
            )
        return result

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
        include_unchecked: bool = False,
    ) -> ModuleResult:
        result = self.scan(progress)
        result.dry_run = dry_run
        items = [item for item in result.items if allow_item(item.id, only_ids)]
        if only_ids is None and not include_unchecked:
            items = [item for item in items if item.default_include]
        result.items = items
        if dry_run:
            result.bytes_freed = result.bytes_estimate
            for item in result.items:
                result.actions.append(f"Would clean {item.label}")
            return result

        admin = is_admin()
        deleted = []
        resetbase = any(item.id == "component_store_resetbase" for item in items)
        store = any(item.id == "component_store" for item in items)
        ran_dism = False
        for item in items:
            if progress:
                progress(f"Cleaning {item.label}")
            if not admin:
                item.detail = "Needs Administrator - not applied (will show again on Scan)"
                result.errors.append(f"{item.id}: needs Administrator")
                continue
            if item.id in {"component_store", "component_store_resetbase"}:
                if ran_dism:
                    result.actions.append(f"Included in DISM cleanup: {item.label}")
                    continue
                cmd = cleanup_command(resetbase=resetbase and (store or item.id == "component_store_resetbase"))
                # If only ResetBase is checked, still run cleanup with the flag.
                if item.id == "component_store" and not resetbase:
                    cmd = cleanup_command(resetbase=False)
                proc = run_hidden(cmd, timeout=60 * 60)
                ran_dism = True
                if proc.returncode == 0:
                    result.actions.append("Ran " + " ".join(cmd[-2:]))
                else:
                    err = (proc.stderr or proc.stdout or "DISM failed").strip()
                    item.detail = err[:500]
                    result.errors.append(f"{item.id}: {err[:300]}")
                continue
            if item.id == "hiberfil":
                proc = run_hidden(["powercfg", "-h", "off"], timeout=120)
                if proc.returncode == 0:
                    result.actions.append("Turned hibernation off")
                else:
                    err = (proc.stderr or proc.stdout or "powercfg failed").strip()
                    item.detail = err[:500]
                    result.errors.append(f"{item.id}: {err[:300]}")
                continue
            if item.id == "shadow_copies":
                used = max(item.bytes_estimate * 2, 320 * 1024 * 1024)
                proc = run_hidden(shadow_resize_command(used), timeout=180)
                if proc.returncode == 0:
                    result.actions.append("Shrank shadow-copy cap")
                else:
                    err = (proc.stderr or proc.stdout or "vssadmin failed").strip()
                    item.detail = err[:500]
                    result.errors.append(f"{item.id}: {err[:300]}")
                continue
            if item.id.startswith("upgrade:"):
                name = item.id.split(":", 1)[1]
                path = next((p for p in upgrade_paths() if p.name == name), None)
                if path is None:
                    continue
                deleted.append(delete_path(path, dry_run=False))
                result.actions.append(f"Deleted {path}")
        merged = merge_results(*deleted) if deleted else None
        if merged:
            result.bytes_freed += merged.bytes_freed
            result.errors.extend(merged.errors)
        return result
