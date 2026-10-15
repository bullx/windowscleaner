"""Extra language packs and a few optional features. Current UI language stays."""

from __future__ import annotations

import ctypes
import json
import locale
import re

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item
from windowscleaner.utils.admin import is_admin
from windowscleaner.utils.proc import run_hidden

_TAG_RE = re.compile(r"~~~([a-z]{2,3}(?:-[a-zA-Z0-9]+)?)~", re.I)

# Names we are willing to remove. SMB1, .NET, and Hyper-V are intentionally absent.
_CAPABILITY_PREFIXES = (
    ("XPS.Viewer", "XPS Viewer"),
    ("App.StepsRecorder", "Steps Recorder"),
    ("Media.WindowsMediaPlayer", "Windows Media Player"),
)
_OPTIONAL_FEATURES = {
    "Printing-XPSServices-Features": "XPS Services",
    "WindowsMediaPlayer": "Windows Media Player",
}


def capability_language_tag(name: str) -> str | None:
    match = _TAG_RE.search(name)
    if not match:
        return None
    if not name.lower().startswith("language."):
        return None
    return match.group(1)


def is_current_ui_language(name: str, keep_tags: set[str]) -> bool:
    tag = capability_language_tag(name)
    if tag is None:
        return False
    return tag.lower() in {item.lower() for item in keep_tags}


def selectable_names(names: list[str], keep_tags: set[str]) -> list[tuple[str, str, str]]:
    """Return (id, label, kind) for capabilities and features this module may remove."""
    chosen: list[tuple[str, str, str]] = []
    for name in names:
        if name in _OPTIONAL_FEATURES:
            chosen.append((f"feature:{name}", _OPTIONAL_FEATURES[name], "feature"))
            continue
        for prefix, label in _CAPABILITY_PREFIXES:
            if name.startswith(prefix):
                chosen.append((f"capability:{name}", label, "capability"))
                break
        else:
            tag = capability_language_tag(name)
            if tag and not is_current_ui_language(name, keep_tags):
                chosen.append((f"capability:{name}", f"Language pack {tag}", "capability"))
    return chosen


def ui_language_tags() -> set[str]:
    tags: set[str] = set()
    kernel = ctypes.windll.kernel32
    for fn_name in ("GetUserDefaultUILanguage", "GetSystemDefaultUILanguage"):
        langid = int(getattr(kernel, fn_name)())
        loc = locale.windows_locale.get(langid & 0xFFFF)
        if loc:
            tags.add(loc.replace("_", "-"))
    return tags


def _ps_json_list(script: str) -> list[str]:
    proc = run_hidden(
        [
            "powershell",
            "-NoProfile",
            "-NoLogo",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=300,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        return [str(item) for item in data if item]
    return []


class WindowsFeaturesModule(CleanModule):
    id = "windows_features"
    label = "Languages & Optional Features"
    description = (
        "Extra language packs, XPS Viewer, Steps Recorder, and legacy Windows Media Player. "
        "The current Windows display language stays. SMB1, .NET, and Hyper-V are not offered. "
        "Included with Debloat."
    )
    risk = Risk.MODERATE
    requires_admin = True
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        keep = ui_language_tags()
        if progress:
            progress("Listing Windows capabilities")
        try:
            capabilities = _ps_json_list(
                "Get-WindowsCapability -Online | Where-Object State -eq Installed "
                "| Select-Object -ExpandProperty Name | ConvertTo-Json -Compress"
            )
            features = _ps_json_list(
                "Get-WindowsOptionalFeature -Online | Where-Object State -eq Enabled "
                "| Select-Object -ExpandProperty FeatureName | ConvertTo-Json -Compress"
            )
        except OSError as exc:
            result.errors.append(str(exc))
            return result
        for item_id, label, kind in selectable_names(capabilities + features, keep):
            result.items.append(
                CleanItem(
                    id=item_id,
                    label=label,
                    detail=item_id.split(":", 1)[1],
                    requires_admin=True,
                    effect=f"Removes optional Windows component: {label}.",
                    repercussions=(
                        "The current display language is not offered. "
                        "Reinstall the feature later from Settings → Optional features. One-way until then."
                    ),
                    risk=self.risk.value,
                )
            )
            _ = kind
        return result

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        result = self.scan(progress)
        result.items = [item for item in result.items if allow_item(item.id, only_ids)]
        result.dry_run = dry_run
        if dry_run:
            for item in result.items:
                result.actions.append(f"Would remove {item.label}")
            return result
        admin = is_admin()
        for item in result.items:
            if progress:
                progress(f"Removing {item.label}")
            if not admin:
                item.detail = "Needs Administrator - not removed (will show again on Scan)"
                result.errors.append(f"{item.id}: needs Administrator")
                continue
            name = item.id.split(":", 1)[1]
            if item.id.startswith("feature:"):
                script = (
                    f"Disable-WindowsOptionalFeature -Online -FeatureName '{name}' -NoRestart | Out-Null"
                )
            else:
                script = f"Remove-WindowsCapability -Online -Name '{name}' | Out-Null"
            proc = run_hidden(
                ["powershell", "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass", "-Command", script],
                timeout=60 * 30,
            )
            if proc.returncode == 0:
                result.actions.append(f"Removed {item.label}")
            else:
                err = (proc.stderr or proc.stdout or "removal failed").strip()
                item.detail = err[:500]
                result.errors.append(f"{item.id}: {err[:300]}")
        return result
