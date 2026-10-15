"""Allowlisted local paths for AI caches, chats, and model weights.

Scan never walks the disk looking for "AI". A row exists only when one of
these paths exists. Parents that hold settings, skills, or logins are not
delete targets — only the children listed here.
"""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.path_rows import PathPlan

# File names that are logins, settings, or keys. Never a delete target.
FORBIDDEN_FILE_NAMES = frozenset(
    {
        "auth.json",
        ".credentials.json",
        "settings.json",
        "settings.local.json",
        "config.toml",
        "config.json",
        "id_ed25519",
        "id_ed25519.pub",
        ".claude.json",
        "mcp.json",
        "mcp_config.json",
        "oauth_creds.json",
        "mcp-oauth-tokens.json",
        "gemini.md",
        "claude.md",
        "keybindings.json",
        "cli-config.json",
        "ide_state.json",
        "argv.json",
        ".gitignore",
        "local state",
        "preferences",
        "cline_mcp_settings.json",
    }
)

# Directory names that hold skills, plugins, or user rules.
FORBIDDEN_DIR_NAMES = frozenset(
    {
        "skills",
        "skills-cursor",
        "plugins",
        "extensions",
        "agents",
        "rules",
        "credentials",
        "config-presets",
        "user-files",
        "snippets",
    }
)

ELECTRON_CACHE_NAMES = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "CachedData",
    "CachedExtensionVSIXs",
    "CachedProfilesData",
    "logs",
    "Crashpad",
    "sentry",
    "process-monitor",
    "blob_storage",
)

_DESKTOP_CACHE_NAMES = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "logs",
    "Crashpad",
)

_MODEL_MAX_FILES = 2_000_000

_CACHE = (
    "Deletes local caches and logs for this app. Quit it first.",
    "The app recreates these. Logins, skills, settings, and the install stay.",
)
_HISTORY = (
    "Deletes local chats and session files for this app.",
    "Local chats are forgotten. Project source, settings, and credentials stay. Cloud chats are not touched.",
)
_MODELS = (
    "Deletes downloaded model weights.",
    "The weights must be downloaded again. The app stays installed. This row starts unchecked.",
)


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _roaming() -> Path:
    return Path(os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming"))


def _local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(_home() / "AppData" / "Local"))


def _temp() -> Path:
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or str(_home() / "Temp"))


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def is_allowed_delete(path: Path) -> bool:
    """Safety net: refuse install dirs, secrets, skills, and settings files."""
    parts = [part.lower() for part in path.parts]
    if "program files" in parts or "program files (x86)" in parts:
        return False
    if path.name.lower() in FORBIDDEN_FILE_NAMES:
        return False
    if any(part in FORBIDDEN_DIR_NAMES for part in parts):
        return False
    return True


def _keep(path: Path) -> Path | None:
    return path if is_allowed_delete(path) else None


def _children(parent: Path, names: tuple[str, ...]) -> list[Path]:
    try:
        if not parent.is_dir():
            return []
        present = {child.name.lower(): child for child in parent.iterdir()}
    except OSError:
        return []
    found: list[Path] = []
    for name in names:
        hit = present.get(name.lower())
        if hit is None:
            continue
        kept = _keep(hit)
        if kept is not None:
            found.append(kept)
    return found


def _glob(directory: Path, pattern: str) -> list[Path]:
    try:
        if not directory.is_dir():
            return []
        matches = list(directory.glob(pattern))
    except OSError:
        return []
    return [p for p in matches if _keep(p) is not None]


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _plan(
    item_id: str,
    label: str,
    paths: list[Path],
    copy: tuple[str, str],
    *,
    default_include: bool = True,
    max_files: int | None = None,
) -> PathPlan | None:
    clean = _dedupe([p for p in paths if is_allowed_delete(p)])
    if not clean:
        return None
    return PathPlan(
        id=item_id,
        label=label,
        paths=clean,
        default_include=default_include,
        effect=copy[0],
        repercussions=copy[1],
        max_files=max_files,
    )


def _add(rows: list[PathPlan], plan: PathPlan | None) -> None:
    if plan is not None:
        rows.append(plan)


def cache_plans() -> list[PathPlan]:
    rows: list[PathPlan] = []
    roaming = _roaming()
    local = _local()
    temp = _temp()
    home = _home()

    _add(
        rows,
        _plan(
            "cursor_roaming_cache",
            "Cursor caches and logs",
            _children(roaming / "Cursor", ELECTRON_CACHE_NAMES),
            _CACHE,
        ),
    )
    _add(
        rows,
        _plan(
            "cursor_temp",
            "Cursor temp and updater logs",
            _children(temp, ("cursor", "cursor-sandbox-cache"))
            + _glob(temp, "cursor-agent-logs-*")
            + _glob(temp, "cursor-inno-updater-*.log"),
            _CACHE,
        ),
    )
    _add(
        rows,
        _plan(
            "cursor_tracking",
            "Cursor local analytics cache",
            _children(home / ".cursor", ("ai-tracking",))
            + _glob(home / ".cursor", "statsig-cache.json*"),
            _CACHE,
        ),
    )

    claude = _env_path("CLAUDE_CONFIG_DIR", home / ".claude")
    _add(
        rows,
        _plan(
            "claude_cache",
            "Claude Code caches and logs",
            _children(
                claude,
                (
                    "cache",
                    "debug",
                    "logs",
                    "paste-cache",
                    "shell-snapshots",
                    "session-env",
                    "statsig",
                    "todos",
                ),
            ),
            _CACHE,
        ),
    )
    claude_temp = _env_path("CLAUDE_CODE_TMPDIR", temp / "claude")
    _add(rows, _plan("claude_temp", "Claude Code temp", _existing_dir(claude_temp), _CACHE))
    for root, label, item_id in (
        (roaming / "Claude", "Claude Desktop caches", "claude_desktop_cache"),
        (local / "AnthropicClaude", "Claude Desktop local caches", "claude_desktop_cache_local"),
    ):
        _add(rows, _plan(item_id, label, _children(root, _DESKTOP_CACHE_NAMES), _CACHE))

    codex = _env_path("CODEX_HOME", home / ".codex")
    _add(
        rows,
        _plan(
            "codex_cache",
            "Codex caches and logs",
            _children(codex, ("logs", "log", "cache", "tmp")),
            _CACHE,
        ),
    )

    gemini = home / ".gemini"
    _add(rows, _plan("gemini_tmp", "Gemini CLI temp", _existing_dir(gemini / "tmp"), _CACHE))

    copilot_cache = _env_path("COPILOT_CACHE_HOME", local / "copilot")
    # Children only, so a config file sitting beside the cache is not removed.
    _add(
        rows,
        _plan("copilot_cache", "GitHub Copilot CLI cache", _direct_children(copilot_cache), _CACHE),
    )

    _add(
        rows,
        _plan(
            "windsurf_cache",
            "Windsurf caches and logs",
            _children(roaming / "Windsurf", _DESKTOP_CACHE_NAMES),
            _CACHE,
        ),
    )
    _add(
        rows,
        _plan(
            "continue_index",
            "Continue index cache",
            _existing_dir(home / ".continue" / "index"),
            _CACHE,
        ),
    )
    _add(rows, _plan("aider_cache", "Aider cache files", _aider_caches(home), _CACHE))

    for root, label, item_id in (
        (roaming / "ChatGPT", "ChatGPT desktop caches", "chatgpt_cache"),
        (roaming / "com.openai.chat", "ChatGPT desktop caches (alt)", "chatgpt_cache_alt"),
    ):
        _add(rows, _plan(item_id, label, _children(root, _DESKTOP_CACHE_NAMES), _CACHE))

    _add(rows, _plan("jetbrains_ai_cache", "JetBrains AI logs", _jetbrains_ai(local), _CACHE))
    _add(
        rows,
        _plan(
            "ollama_logs",
            "Ollama logs",
            _glob(local / "Ollama", "*.log") + _children(local / "Ollama", ("upgrade.log",)),
            _CACHE,
        ),
    )
    _add(
        rows,
        _plan(
            "lmstudio_cache",
            "LM Studio caches and server logs",
            _children(roaming / "LM Studio", _DESKTOP_CACHE_NAMES)
            + _existing_dir(home / ".lmstudio" / "server-logs"),
            _CACHE,
        ),
    )
    return rows


def history_plans() -> list[PathPlan]:
    rows: list[PathPlan] = []
    roaming = _roaming()
    local = _local()
    home = _home()

    gs = roaming / "Cursor" / "User" / "globalStorage"
    _add(
        rows,
        _plan(
            "cursor_global_state",
            "Cursor global chat database",
            _children(
                gs,
                (
                    "state.vscdb",
                    "state.vscdb-shm",
                    "state.vscdb-wal",
                    "anysphere.cursor-agent-host",
                    "anysphere.cursor-agent-worker",
                    "anysphere.cursor-commits",
                ),
            ),
            _HISTORY,
        ),
    )
    _add(
        rows,
        _plan(
            "cursor_workspace_storage",
            "Cursor workspace chat state",
            _existing_dir(roaming / "Cursor" / "User" / "workspaceStorage"),
            _HISTORY,
        ),
    )
    dot = home / ".cursor"
    for name, label, item_id in (
        ("projects", "Cursor agent transcripts", "cursor_dot_projects"),
        ("chats", "Cursor chats", "cursor_chats"),
        ("acp-sessions", "Cursor agent sessions", "cursor_acp_sessions"),
        ("plans", "Cursor plans", "cursor_plans"),
    ):
        _add(rows, _plan(item_id, label, _existing_dir(dot / name), _HISTORY))
    _add(
        rows,
        _plan(
            "cursor_agent_stores",
            "Cursor agent stores",
            _existing_dir(local / "Cursor" / "AgentStores"),
            _HISTORY,
        ),
    )

    claude = _env_path("CLAUDE_CONFIG_DIR", home / ".claude")
    _add(rows, _plan("claude_sessions", "Claude Code sessions", _claude_session_paths(claude), _HISTORY))
    for root, label, item_id in (
        (roaming / "Claude", "Claude Desktop chats", "claude_desktop_chats"),
        (local / "AnthropicClaude", "Claude Desktop local chats", "claude_desktop_chats_local"),
    ):
        _add(
            rows,
            _plan(
                item_id,
                label,
                _children(root, ("Local Storage", "IndexedDB", "Session Storage", "Network")),
                _HISTORY,
            ),
        )
    _add(rows, _plan("claude_store_chats", "Claude Store app chats", _claude_store_chats(local), _HISTORY))

    codex = _env_path("CODEX_HOME", home / ".codex")
    _add(
        rows,
        _plan(
            "codex_sessions",
            "Codex sessions",
            _existing_dir(codex / "sessions") + _glob(codex, "state_*.sqlite*"),
            _HISTORY,
        ),
    )
    _add(
        rows,
        _plan(
            "gemini_chats",
            "Gemini CLI chats",
            _glob(home / ".gemini" / "tmp", "*/chats") + _glob(home / ".gemini" / "tmp", "*/*/chats"),
            _HISTORY,
        ),
    )
    copilot = _env_path("COPILOT_HOME", home / ".copilot")
    _add(
        rows,
        _plan(
            "copilot_sessions",
            "GitHub Copilot CLI sessions",
            _children(copilot, ("session-state", "otel")),
            _HISTORY,
        ),
    )
    code_gs = roaming / "Code" / "User" / "globalStorage"
    _add(
        rows,
        _plan(
            "vscode_ai_chats",
            "VS Code Copilot / Cline / Continue chats",
            _children(
                code_gs,
                (
                    "github.copilot-chat",
                    "github.copilot",
                    "saoudrizwan.claude-dev",
                    "continue.continue",
                    "rooveterinaryinc.roo-cline",
                ),
            ),
            _HISTORY,
        ),
    )
    _add(
        rows,
        _plan(
            "windsurf_history",
            "Windsurf chats",
            _windsurf_history(home),
            _HISTORY,
        ),
    )
    _add(
        rows,
        _plan(
            "continue_sessions",
            "Continue sessions",
            _existing_dir(home / ".continue" / "sessions"),
            _HISTORY,
        ),
    )
    _add(rows, _plan("cline_sessions", "Cline sessions", _cline_sessions(home / ".cline"), _HISTORY))
    for root, label, item_id in (
        (roaming / "ChatGPT", "ChatGPT desktop chats", "chatgpt_chats"),
        (roaming / "com.openai.chat", "ChatGPT desktop chats (alt)", "chatgpt_chats_alt"),
    ):
        _add(
            rows,
            _plan(item_id, label, _children(root, ("Local Storage", "IndexedDB")), _HISTORY),
        )
    _add(
        rows,
        _plan(
            "lmstudio_chats",
            "LM Studio conversations",
            _existing_dir(home / ".lmstudio" / "conversations"),
            _HISTORY,
        ),
    )
    return rows


def model_plans() -> list[PathPlan]:
    home = _home()
    rows: list[PathPlan] = []
    _add(
        rows,
        _plan(
            "ollama_models",
            "Ollama model weights",
            _existing_dir(home / ".ollama" / "models"),
            _MODELS,
            default_include=False,
            max_files=_MODEL_MAX_FILES,
        ),
    )
    _add(
        rows,
        _plan(
            "lmstudio_models",
            "LM Studio model weights",
            _existing_dir(home / ".lmstudio" / "models") + _existing_dir(home / ".lmstudio" / "hub"),
            _MODELS,
            default_include=False,
            max_files=_MODEL_MAX_FILES,
        ),
    )
    return rows


def all_delete_paths() -> list[Path]:
    paths: list[Path] = []
    for plan in cache_plans() + history_plans() + model_plans():
        paths.extend(plan.paths)
    return paths


def _direct_children(path: Path) -> list[Path]:
    try:
        if not path.is_dir():
            return []
        return [child for child in path.iterdir() if _keep(child) is not None]
    except OSError:
        return []


def _existing_dir(path: Path) -> list[Path]:
    kept = _keep(path)
    if kept is None:
        return []
    try:
        if kept.exists():
            return [kept]
    except OSError:
        return []
    return []


def _claude_session_paths(home: Path) -> list[Path]:
    """Children of projects except each project's memory folder, plus session files."""
    found: list[Path] = []
    projects = home / "projects"
    try:
        if projects.is_dir():
            for project in projects.iterdir():
                if not project.is_dir():
                    kept = _keep(project)
                    if kept is not None:
                        found.append(kept)
                    continue
                try:
                    children = list(project.iterdir())
                except OSError:
                    continue
                for child in children:
                    if child.name.lower() == "memory":
                        continue
                    kept = _keep(child)
                    if kept is not None:
                        found.append(kept)
    except OSError:
        pass
    for name in (
        "history.jsonl",
        "file-history",
        "plans",
        "tasks",
        "sessions",
        "image-cache",
        "uploads",
        "usage-data",
        "dev-mods",
        "feedback",
        "feedback-bundles",
    ):
        found.extend(_existing_dir(home / name))
    return found


def _claude_store_chats(local: Path) -> list[Path]:
    packages = local / "Packages"
    found: list[Path] = []
    try:
        if not packages.is_dir():
            return found
        for folder in packages.iterdir():
            name = folder.name.lower()
            if not (name.startswith("claude_") or "anthropic" in name and "claude" in name):
                continue
            for part in ("LocalState", "LocalCache"):
                found.extend(_existing_dir(folder / part))
    except OSError:
        return found
    return found


def _windsurf_history(home: Path) -> list[Path]:
    found: list[Path] = []
    codeium = home / ".codeium" / "windsurf"
    try:
        if codeium.is_dir():
            for child in codeium.iterdir():
                low = child.name.lower()
                if any(token in low for token in ("memory", "chat", "dump")):
                    kept = _keep(child)
                    if kept is not None:
                        found.append(kept)
    except OSError:
        pass
    windsurf = home / ".windsurf"
    try:
        if windsurf.is_dir():
            for child in windsurf.iterdir():
                if child.name.lower() in {"rules", "mcp_config.json"}:
                    continue
                kept = _keep(child)
                if kept is not None:
                    found.append(kept)
    except OSError:
        pass
    return found


def _cline_sessions(root: Path) -> list[Path]:
    return _children(root, ("data", "sessions", "session"))


def _aider_caches(home: Path) -> list[Path]:
    found: list[Path] = []
    try:
        for path in home.glob(".aider*"):
            if path.is_file() and "cache" in path.name.lower() and _keep(path) is not None:
                found.append(path)
    except OSError:
        return found
    return found


def _jetbrains_ai(local: Path) -> list[Path]:
    root = local / "JetBrains"
    found: list[Path] = []
    try:
        if not root.is_dir():
            return found
        for ide in root.iterdir():
            if not ide.is_dir():
                continue
            found.extend(_existing_dir(ide / "llm-jcp-outbox"))
            found.extend(_existing_dir(ide / "event-log-metadata" / "llmc"))
    except OSError:
        return found
    return found
