"""Browser cache cleanup. Cookies, history, and passwords are a different module."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import PathPlan, clean_plans, scan_plans

# Cache folders only. Cookies, History, Login Data, and Web Data are never listed.
CACHE_DIR_NAMES = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "GraphiteDawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "cache2",
)

_NEVER = frozenset(
    {
        "cookies",
        "history",
        "login data",
        "web data",
        "bookmarks",
        "preferences",
    }
)


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or "")


def _roaming() -> Path:
    return Path(os.environ.get("APPDATA") or "")


def _is_profile(path: Path) -> bool:
    name = path.name
    return name == "Default" or name.startswith("Profile ") or name == "Guest Profile"


def _cache_dirs(profile: Path) -> list[Path]:
    found: list[Path] = []
    try:
        if not profile.is_dir():
            return found
        present = {child.name.lower(): child for child in profile.iterdir()}
    except OSError:
        return found
    for name in CACHE_DIR_NAMES:
        hit = present.get(name.lower())
        if hit is None or hit.name.lower() in _NEVER:
            continue
        if hit.is_dir():
            found.append(hit)
    return found


def _chromium_caches(user_data: Path) -> list[Path]:
    found: list[Path] = []
    try:
        if not user_data.is_dir():
            return found
        profiles = [child for child in user_data.iterdir() if child.is_dir() and _is_profile(child)]
    except OSError:
        return found
    for profile in profiles:
        found.extend(_cache_dirs(profile))
    return found


def _opera_caches(root: Path) -> list[Path]:
    return _cache_dirs(root)


def _firefox_caches(profiles: Path) -> list[Path]:
    found: list[Path] = []
    try:
        if not profiles.is_dir():
            return found
        for profile in profiles.iterdir():
            cache2 = profile / "cache2"
            if cache2.is_dir():
                found.append(cache2)
    except OSError:
        return found
    return found


def browser_cache_plans() -> list[PathPlan]:
    local = _local()
    roaming = _roaming()
    browsers = (
        ("edge_cache", "Edge caches", _chromium_caches(local / "Microsoft" / "Edge" / "User Data")),
        ("chrome_cache", "Chrome caches", _chromium_caches(local / "Google" / "Chrome" / "User Data")),
        ("brave_cache", "Brave caches", _chromium_caches(local / "BraveSoftware" / "Brave-Browser" / "User Data")),
        ("vivaldi_cache", "Vivaldi caches", _chromium_caches(local / "Vivaldi" / "User Data")),
        ("opera_cache", "Opera caches", _opera_caches(roaming / "Opera Software" / "Opera Stable")),
        ("opera_gx_cache", "Opera GX caches", _opera_caches(roaming / "Opera Software" / "Opera GX Stable")),
        ("firefox_cache", "Firefox caches", _firefox_caches(roaming / "Mozilla" / "Firefox" / "Profiles")),
    )
    rows: list[PathPlan] = []
    for item_id, label, paths in browsers:
        if not paths:
            continue
        rows.append(
            PathPlan(
                id=item_id,
                label=label,
                paths=paths,
                effect="Deletes browser cache files (images, scripts, compiled pages).",
                repercussions="Sites may load slower once. Cookies, history, bookmarks, and passwords stay.",
            )
        )
    return rows


class BrowserCachesModule(CleanModule):
    id = "browser_caches"
    label = "Browser Caches"
    description = (
        "Edge, Chrome, Brave, Opera, Vivaldi, and Firefox cache folders, including extra profiles. "
        "Does not delete cookies, history, bookmarks, or passwords."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, browser_cache_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            browser_cache_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
