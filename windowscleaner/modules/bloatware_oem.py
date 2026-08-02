"""Opt-in OEM AppX + winget inventory / removal (aggressive)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk


@dataclass(frozen=True)
class OemAppxPattern:
    match: str
    label: str
    reason: str


@dataclass(frozen=True)
class WingetTarget:
    """Substring matched against winget list Id or Name."""

    match: str
    label: str
    reason: str


# Store/AppX OEM families (HP / Dell / Lenovo / common vendor stubs).
OEM_APPX: list[OemAppxPattern] = [
    OemAppxPattern("AD2F1837", "HP AppX suite", "HP preinstalled Store packages (AD2F1837.*)."),
    OemAppxPattern("HPPrinterControl", "HP Printer Control", "HP printer companion AppX."),
    OemAppxPattern("HPSmart", "HP Smart", "HP Smart AppX — keep if you print with it."),
    OemAppxPattern("DellInc", "Dell AppX", "Dell preinstalled Store package."),
    OemAppxPattern("DellCustomerConnect", "Dell Customer Connect", "Dell engagement AppX."),
    OemAppxPattern("DellUpdate", "Dell Update (AppX)", "Dell update AppX stub."),
    OemAppxPattern("PortraitDisplays", "Portrait Displays / Dell display", "OEM display helper AppX."),
    OemAppxPattern("E046963F", "Lenovo AppX suite", "Lenovo preinstalled Store packages."),
    OemAppxPattern("LenovoCorporation", "Lenovo Corporation AppX", "Lenovo Store package."),
    OemAppxPattern("LenovoUtility", "Lenovo Utility", "Lenovo utility AppX."),
    OemAppxPattern("McAfee", "McAfee AppX", "McAfee Store stub — prefer vendor remover for full AV."),
    OemAppxPattern("Norton", "Norton AppX", "Norton Store stub — prefer vendor remover for full AV."),
    OemAppxPattern("WildTangent", "WildTangent Games", "OEM game portal."),
    OemAppxPattern("Booking.com", "Booking.com", "OEM travel stub."),
    OemAppxPattern("BubbleWitch", "Bubble Witch (OEM)", "OEM game junk."),
]

# winget Id / Name substrings for common Win32 OEM agents.
WINGET_TARGETS: list[WingetTarget] = [
    WingetTarget("Dell.SupportAssist", "Dell SupportAssist", "Heavy OEM agent; often reinstalls via drivers."),
    WingetTarget("SupportAssist", "SupportAssist (name match)", "Dell SupportAssist variant."),
    WingetTarget("Dell.CommandUpdate", "Dell Command Update", "OEM updater — keep if you rely on Dell drivers."),
    WingetTarget("Dell.DigitalDelivery", "Dell Digital Delivery", "OEM digital delivery agent."),
    WingetTarget("Dell.Optimizer", "Dell Optimizer", "OEM 'optimizer' suite."),
    WingetTarget("Dell.MyDell", "MyDell", "Dell consumer hub."),
    WingetTarget("HP.HPSupportAssistant", "HP Support Assistant", "HP support agent / nags."),
    WingetTarget("HPSupportAssistant", "HP Support Assistant (alt)", "HP support agent variant."),
    WingetTarget("HP.Wolf", "HP Wolf Security", "HP Wolf / Sure Click suite — aggressive."),
    WingetTarget("HPWolf", "HP Wolf (name)", "HP Wolf name match."),
    WingetTarget("HP.Documentation", "HP Documentation", "OEM docs stub."),
    WingetTarget("Lenovo.Vantage", "Lenovo Vantage", "Lenovo hub / telemetry companion."),
    WingetTarget("LenovoVantage", "Lenovo Vantage (alt)", "Lenovo Vantage variant."),
    WingetTarget("Lenovo.SystemUpdate", "Lenovo System Update", "OEM updater — keep if you use Lenovo drivers."),
    WingetTarget("McAfee", "McAfee (winget)", "AV trial — prefer McAfee Consumer Product Removal tool."),
    WingetTarget("Norton", "Norton (winget)", "AV trial — prefer vendor removal tool."),
    WingetTarget("WildTangent", "WildTangent (winget)", "OEM game portal Win32."),
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=flags,
    )


def _run_ps(script: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "powershell",
            "-NoProfile",
            "-NoLogo",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
    )


def _parse_json_list(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _list_appx() -> list[dict]:
    from windowscleaner.utils.admin import is_admin

    scripts = [
        "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress"
    ]
    if is_admin():
        scripts.insert(
            0,
            "Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress",
        )
    for script in scripts:
        proc = _run_ps(script)
        if proc.returncode != 0:
            continue
        pkgs = _parse_json_list(proc.stdout)
        if pkgs:
            return pkgs
    return []


def _appx_matches(pkg: dict, pattern: str) -> bool:
    hay = "|".join(
        str(pkg.get(k) or "") for k in ("Name", "PackageFamilyName", "PackageFullName")
    ).lower()
    return pattern.lower() in hay


def _winget_available() -> bool:
    return shutil.which("winget") is not None


def _list_winget() -> list[tuple[str, str]]:
    """Return list of (id, name) from `winget list`."""
    if not _winget_available():
        return []
    proc = _run(
        [
            "winget",
            "list",
            "--accept-source-agreements",
            "--disable-interactivity",
        ]
    )
    if proc.returncode not in (0,):
        # winget sometimes returns non-zero with partial output
        if not proc.stdout.strip():
            return []
    lines = proc.stdout.splitlines()
    # Skip header until a line of dashes
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"^-{3,}", line.strip()) or (line.strip().startswith("-") and "Name" not in line):
            # find separator after Name / Id header
            if set(line.strip()) <= {"-", " "}:
                start = i + 1
                break
    rows: list[tuple[str, str]] = []
    for line in lines[start:]:
        if not line.strip():
            continue
        # winget columns are space-padded; Id is usually 2nd token group
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2:
            continue
        name, pkg_id = parts[0], parts[1]
        if name.lower() == "name" or pkg_id.lower() == "id":
            continue
        rows.append((pkg_id, name))
    return rows


class BloatwareOemModule(CleanModule):
    id = "bloatware_oem"
    label = "OEM / Win32 Bloat (opt-in)"
    description = (
        "Scans HP / Dell / Lenovo AppX families and common winget-listed OEM agents "
        "(SupportAssist, HP Support Assistant, Lenovo Vantage, AV trials). "
        "Aggressive and opt-in — never part of Standard. Some OEM tools reinstall "
        "via BIOS/drivers; McAfee/Norton prefer vendor removers."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        if progress:
            progress("Scanning OEM AppX packages...")
        seen_appx: set[str] = set()
        for pkg in _list_appx():
            full = str(pkg.get("PackageFullName") or "")
            if not full or full in seen_appx:
                continue
            for pat in OEM_APPX:
                if _appx_matches(pkg, pat.match):
                    seen_appx.add(full)
                    result.items.append(
                        CleanItem(
                            id=f"appx:{full}",
                            label=pat.label,
                            detail=f"AppX — {pkg.get('Name')} — {pat.reason}",
                            bytes_estimate=0,
                            requires_admin=True,
                            effect=f"Uninstalls OEM AppX: {pat.label}.",
                            repercussions=(
                                "Store package removed. OEM may re-push via drivers/BIOS. "
                                "Reinstall from Store/OEM if needed."
                            ),
                        )
                    )
                    break

        if progress:
            progress("Scanning winget installed packages...")
        if not _winget_available():
            result.errors.append(
                "winget not found — Win32 OEM scan skipped "
                "(install App Installer from Microsoft Store). AppX OEM matches still listed."
            )
            return result

        seen_winget: set[str] = set()
        for pkg_id, name in _list_winget():
            hay = f"{pkg_id}|{name}".lower()
            for target in WINGET_TARGETS:
                if target.match.lower() not in hay:
                    continue
                key = pkg_id or name
                if key in seen_winget:
                    break
                seen_winget.add(key)
                result.items.append(
                    CleanItem(
                        id=f"winget:{pkg_id}",
                        label=target.label,
                        detail=f"winget — {name} ({pkg_id}) — {target.reason}",
                        bytes_estimate=0,
                        requires_admin=True,
                        effect=f"Uninstalls via winget: {target.label}.",
                        repercussions=(
                            "Win32 uninstall attempted. Leftover services/tasks may remain. "
                            "AV suites: prefer vendor removal tools. OEM may reinstall."
                        ),
                    )
                )
                break

        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        result = self.scan(progress)
        result.dry_run = dry_run
        admin = is_admin()

        for item in result.items:
            if progress:
                progress(f"{'Would remove' if dry_run else 'Removing'} {item.label}")
            if dry_run:
                result.actions.append(f"Would remove {item.id}")
                continue
            if not admin:
                item.detail = "Needs Administrator - not removed (will show again on Scan)"
                item.repercussions = "Run Restart as Administrator, then Clean again."
                result.errors.append(f"{item.id}: needs Administrator")
                continue

            if item.id.startswith("appx:"):
                full = item.id.split(":", 1)[1].replace("'", "''")
                script = (
                    f"Get-AppxPackage -AllUsers | "
                    f"Where-Object {{ $_.PackageFullName -eq '{full}' }} | "
                    f"Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue; "
                    f"Get-AppxPackage | "
                    f"Where-Object {{ $_.PackageFullName -eq '{full}' }} | "
                    f"Remove-AppxPackage -ErrorAction SilentlyContinue; "
                    f"'DONE'"
                )
                proc = _run_ps(script)
                if proc.returncode == 0:
                    result.actions.append(f"Removed AppX {item.label}")
                else:
                    err = proc.stderr.strip() or proc.stdout.strip() or "failed"
                    result.errors.append(f"{item.label}: {err}")
                continue

            if item.id.startswith("winget:"):
                pkg_id = item.id.split(":", 1)[1]
                proc = _run(
                    [
                        "winget",
                        "uninstall",
                        "--id",
                        pkg_id,
                        "--silent",
                        "--accept-source-agreements",
                        "--disable-interactivity",
                        "--force",
                    ]
                )
                if proc.returncode == 0:
                    result.actions.append(f"Uninstalled via winget: {item.label} ({pkg_id})")
                else:
                    # Fallback: try by name from detail
                    err = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
                    result.errors.append(f"{item.label}: {err}")

        return result
