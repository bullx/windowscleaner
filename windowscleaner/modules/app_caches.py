"""Chat, launcher, and extracted-driver caches. Logins and game installs stay."""

from __future__ import annotations

import os
import re
import winreg
from pathlib import Path

from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import PathPlan, clean_plans, scan_plans

_ELECTRON = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "logs",
    "Crashpad",
)

_LOGIN_NAMES = frozenset(
    {
        "local storage",
        "indexeddb",
        "session storage",
        "local state",
        "cookies",
        "login data",
    }
)

_EFFECT = "Deletes regenerating cache files for this app."
_REPER = "The app may load slower once. Login databases and the install stay. Quit the app first."


def _roaming() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming"))


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))


def _children_named(parent: Path, names: tuple[str, ...]) -> list[Path]:
    try:
        if not parent.is_dir():
            return []
        present = {child.name.lower(): child for child in parent.iterdir()}
    except OSError:
        return []
    found: list[Path] = []
    for name in names:
        hit = present.get(name.lower())
        if hit is not None and hit.name.lower() not in _LOGIN_NAMES:
            found.append(hit)
    return found


def _electron_caches(root: Path) -> list[Path]:
    """Cache folders under an Electron app root, not Local Storage or IndexedDB."""
    found = _children_named(root, _ELECTRON)
    local_cache = root / "LocalCache"
    found.extend(_children_named(local_cache, _ELECTRON))
    try:
        if local_cache.is_dir():
            for child in local_cache.iterdir():
                found.extend(_children_named(child, _ELECTRON))
                found.extend(_children_named(child / "Default", _ELECTRON))
    except OSError:
        pass
    return found


def _package_dirs(local: Path, prefix: str) -> list[Path]:
    packages = local / "Packages"
    found: list[Path] = []
    try:
        if not packages.is_dir():
            return found
        for folder in packages.iterdir():
            if folder.is_dir() and folder.name.lower().startswith(prefix.lower()):
                found.append(folder)
    except OSError:
        return found
    return found


def _steam_libraries() -> list[Path]:
    roots: list[Path] = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _typ = winreg.QueryValueEx(key, "SteamPath")
            if value:
                roots.append(Path(str(value)))
    except OSError:
        pass
    for candidate in (
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
    ):
        if candidate not in roots:
            roots.append(candidate)

    libraries: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        steamapps = root / "steamapps"
        if steamapps.is_dir():
            key = str(steamapps).lower()
            if key not in seen:
                seen.add(key)
                libraries.append(steamapps)
        vdf = steamapps / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"([A-Za-z]:[^"]+)"', text):
            raw = match.group(1).replace("\\\\", "\\")
            lib = Path(raw)
            apps = lib / "steamapps"
            key = str(apps).lower()
            if key not in seen:
                seen.add(key)
                libraries.append(apps)
    return libraries


def _steam_caches() -> list[Path]:
    found: list[Path] = []
    for steamapps in _steam_libraries():
        for name in ("shadercache", "downloading"):
            path = steamapps / name
            # steamapps\common is the game install and is never added.
            if path.is_dir() and "common" not in {part.lower() for part in path.parts}:
                found.append(path)
    return found


def _drive_extracts() -> list[Path]:
    """Extracted NVIDIA/AMD/Intel driver folders at the drive root, not Program Files."""
    system = os.environ.get("SystemDrive", "C:")
    if not system.endswith(":"):
        system = system + ":"
    root = Path(system + "\\")
    found: list[Path] = []
    for name in ("NVIDIA", "AMD", "Intel"):
        path = root / name
        parts = {part.lower() for part in path.parts}
        if "program files" in parts or "program files (x86)" in parts:
            continue
        try:
            if path.is_dir():
                found.append(path)
        except OSError:
            continue
    return found


def app_cache_plans() -> list[PathPlan]:
    roaming = _roaming()
    local = _local()
    rows: list[PathPlan] = []

    apps = (
        ("discord_cache", "Discord caches", roaming / "discord"),
        ("discord_canary_cache", "Discord Canary caches", roaming / "discordcanary"),
        ("slack_cache", "Slack caches", roaming / "Slack"),
        ("zoom_cache", "Zoom caches", roaming / "Zoom"),
        ("teams_classic_cache", "Teams classic caches", roaming / "Microsoft" / "Teams"),
    )
    for item_id, label, root in apps:
        paths = _electron_caches(root)
        if paths:
            rows.append(PathPlan(id=item_id, label=label, paths=paths, effect=_EFFECT, repercussions=_REPER))

    for folder in _package_dirs(local, "MSTeams_"):
        paths = _electron_caches(folder)
        if paths:
            rows.append(
                PathPlan(
                    id="teams_cache",
                    label="New Teams caches",
                    paths=paths,
                    effect=_EFFECT,
                    repercussions=_REPER,
                )
            )
            break

    spotify_paths = _children_named(local / "Spotify", ("Storage",))
    spotify_paths.extend(_electron_caches(roaming / "Spotify"))
    for folder in _package_dirs(local, "SpotifyAB.SpotifyMusic"):
        spotify_paths.extend(_electron_caches(folder))
    if spotify_paths:
        rows.append(
            PathPlan(
                id="spotify_cache",
                label="Spotify caches",
                paths=spotify_paths,
                effect=_EFFECT,
                repercussions=_REPER,
            )
        )

    epic = local / "EpicGamesLauncher" / "Saved"
    epic_paths: list[Path] = []
    try:
        if epic.is_dir():
            epic_paths = [p for p in epic.glob("webcache*") if p.is_dir()]
    except OSError:
        epic_paths = []
    if epic_paths:
        rows.append(
            PathPlan(
                id="epic_cache",
                label="Epic Games web cache",
                paths=epic_paths,
                effect=_EFFECT,
                repercussions="Launcher web cache only. Installed games stay.",
            )
        )

    bnet = _children_named(local / "Battle.net", ("Cache",)) + _children_named(
        roaming / "Battle.net", ("BrowserCache", "Cache")
    )
    if bnet:
        rows.append(
            PathPlan(
                id="battlenet_cache",
                label="Battle.net caches",
                paths=bnet,
                effect=_EFFECT,
                repercussions="Launcher cache only. Installed games stay.",
            )
        )

    steam = _steam_caches()
    if steam:
        rows.append(
            PathPlan(
                id="steam_shader_cache",
                label="Steam shader cache and download staging",
                paths=steam,
                effect="Deletes Steam shadercache and leftover download staging.",
                repercussions="Games in steamapps\\common and save games stay. Shaders rebuild later.",
            )
        )

    extracts = _drive_extracts()
    if extracts:
        rows.append(
            PathPlan(
                id="driver_extracts",
                label="Extracted driver setup folders",
                paths=extracts,
                effect="Deletes NVIDIA, AMD, or Intel driver extracts at the drive root.",
                repercussions=(
                    "Does not touch C:\\Program Files. The vendor installer can extract these again. "
                    "One-way for the files currently in that folder."
                ),
            )
        )
    return rows


class AppCachesModule(CleanModule):
    id = "app_caches"
    label = "App Caches"
    description = (
        "Discord, Slack, Zoom, Teams, Spotify, Steam shader cache, Epic and Battle.net "
        "web caches, and extracted NVIDIA/AMD/Intel driver folders at the drive root. "
        "Login databases and game installs stay."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, app_cache_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            app_cache_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
