"""Opt-in browser cookies and history. This logs you out of sites. Not part of Free disk."""

from __future__ import annotations

from pathlib import Path

from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.browser_caches import _is_profile, _local, _roaming
from windowscleaner.modules.path_rows import PathPlan, clean_plans, scan_plans

_CHROMIUM_FILES = (
    "Cookies",
    "Cookies-journal",
    "History",
    "History-journal",
    "Visited Links",
    "Top Sites",
    "Top Sites-journal",
    "Web Data",
    "Web Data-journal",
    "Favicons",
    "Favicons-journal",
)
_NETWORK_FILES = ("Cookies", "Cookies-journal")


def _files_in(folder: Path, names: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    try:
        if not folder.is_dir():
            return found
        present = {child.name.lower(): child for child in folder.iterdir()}
    except OSError:
        return found
    for name in names:
        hit = present.get(name.lower())
        if hit is not None and hit.is_file():
            found.append(hit)
    return found


def _chromium_privacy(user_data: Path) -> list[Path]:
    found: list[Path] = []
    try:
        if not user_data.is_dir():
            return found
        profiles = [child for child in user_data.iterdir() if child.is_dir() and _is_profile(child)]
    except OSError:
        return found
    for profile in profiles:
        found.extend(_files_in(profile, _CHROMIUM_FILES))
        found.extend(_files_in(profile / "Network", _NETWORK_FILES))
    return found


def _opera_privacy(root: Path) -> list[Path]:
    return _files_in(root, _CHROMIUM_FILES) + _files_in(root / "Network", _NETWORK_FILES)


def _firefox_privacy(profiles: Path) -> list[Path]:
    found: list[Path] = []
    try:
        if not profiles.is_dir():
            return found
        for profile in profiles.iterdir():
            if not profile.is_dir():
                continue
            for name in ("cookies.sqlite", "cookies.sqlite-wal", "places.sqlite", "places.sqlite-wal"):
                path = profile / name
                if path.is_file():
                    found.append(path)
    except OSError:
        return found
    return found


def browser_privacy_plans() -> list[PathPlan]:
    local = _local()
    roaming = _roaming()
    rows_src = (
        ("edge_privacy", "Edge cookies and history", _chromium_privacy(local / "Microsoft" / "Edge" / "User Data")),
        ("chrome_privacy", "Chrome cookies and history", _chromium_privacy(local / "Google" / "Chrome" / "User Data")),
        ("brave_privacy", "Brave cookies and history", _chromium_privacy(local / "BraveSoftware" / "Brave-Browser" / "User Data")),
        ("vivaldi_privacy", "Vivaldi cookies and history", _chromium_privacy(local / "Vivaldi" / "User Data")),
        (
            "opera_privacy",
            "Opera cookies and history",
            _opera_privacy(roaming / "Opera Software" / "Opera Stable"),
        ),
        ("firefox_privacy", "Firefox cookies and history", _firefox_privacy(roaming / "Mozilla" / "Firefox" / "Profiles")),
    )
    reper = "Logs you out of websites and clears browsing history. Bookmarks file is kept. Not part of Free disk."
    rows: list[PathPlan] = []
    for item_id, label, paths in rows_src:
        if paths:
            rows.append(
                PathPlan(
                    id=item_id,
                    label=label,
                    paths=paths,
                    effect="Deletes cookies and browsing history for this browser.",
                    repercussions=reper,
                )
            )
    return rows


class BrowserPrivacyModule(CleanModule):
    id = "browser_privacy"
    label = "Browser Cookies & History"
    description = (
        "Cookies and history for Edge, Chrome, Brave, Opera, Vivaldi, and Firefox. "
        "This logs you out of sites. Opt-in, and not part of Free disk."
    )
    risk = Risk.MODERATE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, browser_privacy_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            browser_privacy_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
