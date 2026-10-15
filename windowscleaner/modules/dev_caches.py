"""Developer tool caches. Project folders, Cargo registry, and NuGet packages stay."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import PathPlan, clean_plans, scan_plans

_EFFECT = "Deletes a developer tool cache that the next build can recreate."
_REPER = (
    "The next build or install re-downloads what it needs. "
    "Project folders, node_modules, Cargo registry sources, and NuGet packages stay."
)


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or str(Path.home()))


def _roaming() -> Path:
    return Path(os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming"))


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(_home() / "AppData" / "Local"))


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _safe(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if "node_modules" in parts:
        return False
    if "program files" in parts or "program files (x86)" in parts:
        return False
    # Cargo registry sources and the NuGet global packages folder are not HTTP caches.
    if path.name.lower() == "registry" and path.parent.name.lower() == ".cargo":
        return False
    if path.name.lower() == "packages" and ".nuget" in parts:
        return False
    return True


def dev_cache_plans() -> list[PathPlan]:
    home = _home()
    local = _local()
    roaming = _roaming()
    candidates = (
        ("npm_cache", "npm cache", roaming / "npm-cache"),
        ("npm_cache_local", "npm cache (local)", local / "npm-cache"),
        ("pip_cache", "pip cache", local / "pip" / "Cache"),
        ("nuget_http_cache", "NuGet HTTP cache", local / "NuGet" / "v3-cache"),
        ("nuget_http_cache_alt", "NuGet HTTP cache (alt)", local / "NuGet" / "Cache"),
        ("gradle_cache", "Gradle caches", home / ".gradle" / "caches"),
        ("go_build_cache", "Go build cache", local / "go-build"),
        ("yarn_cache", "Yarn cache", local / "Yarn" / "Cache"),
        ("pnpm_store", "pnpm store", local / "pnpm" / "store"),
        ("pnpm_store_home", "pnpm store (home)", home / ".pnpm-store"),
        ("cargo_git", "Cargo git checkouts", home / ".cargo" / "git"),
    )
    rows: list[PathPlan] = []
    for item_id, label, path in candidates:
        if not _safe(path) or not _exists(path):
            continue
        rows.append(PathPlan(id=item_id, label=label, paths=[path], effect=_EFFECT, repercussions=_REPER))
    return rows


class DevCachesModule(CleanModule):
    id = "dev_caches"
    label = "Developer Caches"
    description = (
        "npm, pip, NuGet HTTP cache, Gradle, Go build cache, Yarn, pnpm, and Cargo git checkouts. "
        "Does not delete project folders, node_modules, Cargo registry sources, or NuGet packages."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, dev_cache_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            dev_cache_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
