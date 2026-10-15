"""Docker build-cache prune and WSL virtual-disk compact. Rows start unchecked.

Does not delete Docker images the user did not include, and does not delete a WSL distro.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item
from windowscleaner.modules.path_rows import select_plans, PathPlan
from windowscleaner.utils.proc import run_hidden
from windowscleaner.utils.size import format_bytes, path_size

_MODEL_FILES = 2_000_000


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))


def wsl_disks() -> list[Path]:
    """Known WSL ext4.vhdx locations. Does not search the whole disk."""
    local = _local()
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path).lower()
        if key in seen:
            return
        if path.name.lower() != "ext4.vhdx":
            return
        try:
            if path.is_file():
                seen.add(key)
                found.append(path)
        except OSError:
            return

    wsl_root = local / "wsl"
    try:
        if wsl_root.is_dir():
            for path in wsl_root.glob("*/ext4.vhdx"):
                add(path)
            for path in wsl_root.glob("*/*/ext4.vhdx"):
                add(path)
    except OSError:
        pass

    packages = local / "Packages"
    try:
        if packages.is_dir():
            for path in packages.glob("*/LocalState/ext4.vhdx"):
                add(path)
    except OSError:
        pass
    return found


def _docker_build_cache_bytes() -> int:
    proc = run_hidden(["docker", "system", "df"], timeout=60)
    if proc.returncode != 0:
        return 0
    for line in proc.stdout.splitlines():
        low = line.lower()
        if "build cache" not in low:
            continue
        # TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
        parts = line.split()
        for token in reversed(parts):
            size = _parse_docker_size(token)
            if size:
                return size
    return 0


def _parse_docker_size(token: str) -> int:
    token = token.strip().upper().replace("IB", "B")
    if token.endswith("GB"):
        return int(float(token[:-2]) * 1024**3)
    if token.endswith("MB"):
        return int(float(token[:-2]) * 1024**2)
    if token.endswith("KB"):
        return int(float(token[:-2]) * 1024)
    if token.endswith("B") and token[:-1].replace(".", "", 1).isdigit():
        return int(float(token[:-1]))
    return 0


def _plans() -> list[PathPlan]:
    rows: list[PathPlan] = []
    try:
        cache_bytes = _docker_build_cache_bytes()
    except OSError:
        cache_bytes = 0
    if cache_bytes > 0:
        rows.append(
            PathPlan(
                id="docker_build_cache",
                label="Docker build cache",
                paths=[],
                default_include=False,
                effect="Runs docker builder prune to drop unused build cache.",
                repercussions=(
                    "Build cache is removed. Images and containers you did not include stay. "
                    "The next image build is slower until the cache refills."
                ),
            )
        )
        rows[-1].max_files = cache_bytes  # stash size; paths empty, scan handles it
    for disk in wsl_disks():
        rows.append(
            PathPlan(
                id=f"wsl:{disk}",
                label=f"WSL virtual disk ({disk.parent.name})",
                paths=[disk],
                default_include=False,
                max_files=_MODEL_FILES,
                effect="Compacts this WSL ext4.vhdx. The distro is not deleted.",
                repercussions=(
                    "The Linux distro stays. Compact can take a long time and needs the distro stopped. "
                    "If a process holds the file, it stays on disk."
                ),
            )
        )
    return rows


class DevDisksModule(CleanModule):
    id = "dev_disks"
    label = "Developer Disks"
    description = (
        "Docker build-cache prune and WSL ext4.vhdx compact. Every row starts unchecked. "
        "Does not delete images you did not include, and does not delete the distro."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for plan in _plans():
            if progress:
                progress(f"Scanning {plan.label}")
            if plan.id == "docker_build_cache":
                size = int(plan.max_files or 0)
                if size <= 0:
                    continue
                detail = "docker builder prune (build cache only)"
            else:
                size = path_size(plan.paths[0], max_files=plan.max_files or _MODEL_FILES) if plan.paths else 0
                if size <= 0:
                    continue
                # Id includes the byte size so a successful shrink verifies as Fixed.
                plan = PathPlan(
                    id=f"wsl:{plan.paths[0]}:{size}",
                    label=plan.label,
                    paths=plan.paths,
                    default_include=False,
                    effect=plan.effect,
                    repercussions=plan.repercussions,
                )
                detail = (
                    f"{plan.paths[0]} — distro is kept. "
                    f"Size now {format_bytes(size)}. Compact shrinks the file; it does not delete it."
                )
            result.items.append(
                CleanItem(
                    id=plan.id,
                    label=plan.label,
                    detail=detail,
                    bytes_estimate=size,
                    default_include=False,
                    effect=plan.effect,
                    repercussions=plan.repercussions,
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
        scanned = self.scan(progress)
        dummy = [
            PathPlan(id=item.id, label=item.label, default_include=item.default_include)
            for item in scanned.items
        ]
        allowed = {p.id for p in select_plans(dummy, only_ids, include_unchecked=include_unchecked)}
        items = [item for item in scanned.items if item.id in allowed and allow_item(item.id, only_ids)]
        result = ModuleResult(module_id=self.id, label=self.label, dry_run=dry_run, items=items)
        for item in items:
            if progress:
                progress(f"{'Would compact' if dry_run else 'Compacting'} {item.label}")
            if dry_run:
                result.actions.append(f"Would clean {item.label}")
                result.bytes_freed += item.bytes_estimate
                continue
            if item.id == "docker_build_cache":
                proc = run_hidden(["docker", "builder", "prune", "-af"], timeout=60 * 30)
                if proc.returncode == 0:
                    result.actions.append("Pruned Docker build cache")
                    result.bytes_freed += item.bytes_estimate
                else:
                    err = (proc.stderr or proc.stdout or "docker builder prune failed").strip()
                    item.detail = err
                    result.errors.append(f"{item.id}: {err}")
                continue
            disk = _disk_from_id(item.id)
            if disk is None:
                result.errors.append(f"{item.id}: missing disk path")
                continue
            ok, msg = _compact_vhdx(disk, progress)
            if ok:
                result.actions.append(msg)
                result.bytes_freed += item.bytes_estimate
            else:
                item.detail = msg
                result.errors.append(f"{item.id}: {msg}")
        _ = chosen_ids
        return result


def _disk_from_id(item_id: str) -> Path | None:
    # wsl:<path>:<size>
    if not item_id.startswith("wsl:"):
        return None
    body = item_id[4:]
    path_text, _sep, _size = body.rpartition(":")
    # Windows paths contain a drive-letter colon. rpartition splits the size suffix.
    if not path_text:
        return None
    return Path(path_text)


def _compact_vhdx(disk: Path, progress: ProgressCb | None) -> tuple[bool, str]:
    if progress:
        progress("Stopping WSL so the virtual disk can compact...")
    run_hidden(["wsl", "--shutdown"], timeout=120)
    script = "\n".join(
        [
            f'select vdisk file="{disk}"',
            "attach vdisk readonly",
            "compact vdisk",
            "detach vdisk",
            "exit",
        ]
    )
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            script_path = handle.name
    except OSError as exc:
        return False, str(exc)
    try:
        proc = run_hidden(["diskpart", "/s", script_path], timeout=60 * 60)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if proc.returncode == 0 and "encountered an error" not in (proc.stdout or "").lower():
        return True, f"Compacted {disk.name}; distro kept"
    err = (proc.stderr or proc.stdout or "diskpart compact failed").strip()
    return False, err[:500]
