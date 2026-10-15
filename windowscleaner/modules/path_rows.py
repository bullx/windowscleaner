"""Scan/clean helpers for modules that delete an allowlist of paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from windowscleaner.modules.base import (
    CleanItem,
    CleanModule,
    ModuleResult,
    OnlyIds,
    ProgressCb,
    allow_item,
    filter_items,
)
from windowscleaner.utils.fs import delete_path, merge_results
from windowscleaner.utils.size import path_size


@dataclass
class PathPlan:
    id: str
    label: str
    paths: list[Path] = field(default_factory=list)
    default_include: bool = True
    requires_admin: bool = False
    effect: str = ""
    repercussions: str = ""
    # Model folders need a real size for the confirm dialog.
    max_files: int | None = None


def plan_size(plan: PathPlan) -> int:
    total = 0
    for path in plan.paths:
        if plan.max_files is None:
            total += path_size(path)
        else:
            total += path_size(path, max_files=plan.max_files)
    return total


def _detail(paths: list[Path]) -> str:
    shown = [str(p) for p in paths[:4]]
    extra = len(paths) - len(shown)
    text = "; ".join(shown)
    if extra > 0:
        text += f"; +{extra} more"
    return text


def select_plans(
    plans: list[PathPlan],
    only_ids: OnlyIds,
    *,
    include_unchecked: bool,
) -> list[PathPlan]:
    """GUI passes checked ids. CLI with no ids skips rows that start unchecked."""
    chosen = [p for p in plans if allow_item(p.id, only_ids)]
    if only_ids is None and not include_unchecked:
        chosen = [p for p in chosen if p.default_include]
    return chosen


def scan_plans(
    module: CleanModule,
    plans: list[PathPlan],
    progress: ProgressCb | None = None,
) -> ModuleResult:
    result = ModuleResult(module_id=module.id, label=module.label)
    for plan in plans:
        if progress:
            progress(f"Scanning {plan.label}")
        existing = [p for p in plan.paths if _exists(p)]
        if not existing:
            continue
        size = plan_size(PathPlan(id=plan.id, label=plan.label, paths=existing, max_files=plan.max_files))
        if size <= 0:
            continue
        result.items.append(
            CleanItem(
                id=plan.id,
                label=plan.label,
                detail=_detail(existing),
                bytes_estimate=size,
                requires_admin=plan.requires_admin,
                effect=plan.effect,
                repercussions=plan.repercussions,
                default_include=plan.default_include,
                risk=module.risk.value,
            )
        )
    return result


def clean_plans(
    module: CleanModule,
    plans: list[PathPlan],
    *,
    dry_run: bool = False,
    progress: ProgressCb | None = None,
    only_ids: OnlyIds = None,
    include_unchecked: bool = False,
) -> ModuleResult:
    chosen = select_plans(plans, only_ids, include_unchecked=include_unchecked)
    if dry_run:
        result = scan_plans(module, chosen, progress)
        result.items = filter_items(result.items, only_ids)
        if only_ids is None and not include_unchecked:
            result.items = [i for i in result.items if i.default_include]
        result.dry_run = True
        result.bytes_freed = result.bytes_estimate
        for item in result.items:
            result.actions.append(f"Would clean {item.label}")
        return result

    result = ModuleResult(module_id=module.id, label=module.label, dry_run=False)
    deleted = []
    for plan in chosen:
        existing = [p for p in plan.paths if _exists(p)]
        if not existing:
            continue
        item = CleanItem(
            id=plan.id,
            label=plan.label,
            detail=_detail(existing),
            requires_admin=plan.requires_admin,
            effect=plan.effect,
            repercussions=plan.repercussions,
            default_include=plan.default_include,
            risk=module.risk.value,
        )
        result.items.append(item)
        if progress:
            progress(f"Cleaning {plan.label}")
        for path in existing:
            deleted.append(delete_path(path, dry_run=False))
        result.actions.append(f"Cleaned {plan.label}")
    merged = merge_results(*deleted) if deleted else None
    if merged:
        result.bytes_freed = merged.bytes_freed
        result.errors.extend(merged.errors)
    return result


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False
