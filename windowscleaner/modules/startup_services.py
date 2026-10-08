"""Optional Windows services that auto-start or sit in RAM and are not required for a normal desktop.

Never touches Defender, firewall, SmartScreen, Windows Update, BITS, audio, Wi-Fi,
DHCP/DNS, Bluetooth, Windows Hello, Store licensing, or Hyper-V / WSL.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, filter_items


@dataclass(frozen=True)
class StartupService:
    name: str
    label: str
    reason: str
    # disabled = do not start again; demand = Manual, start only if something asks
    target: str
    keep_if: str
    per_user: bool = False


# Inbox services only. Each row is optional and reviewed before Clean.
# SysMain / WSearch stay in perf_services. DiagTrack and the other telemetry
# services stay in telemetry_services — do not duplicate them here.
SERVICES: list[StartupService] = [
    StartupService(
        "Fax",
        "Fax",
        "Windows Fax. Unused on almost every home PC.",
        "disabled",
        "You send faxes from this PC.",
    ),
    StartupService(
        "XblAuthManager",
        "Xbox Live Auth Manager",
        "Signs in to Xbox Live in the background.",
        "disabled",
        "You use the Xbox app, Game Pass, or Xbox cloud saves.",
    ),
    StartupService(
        "XblGameSave",
        "Xbox Live Game Save",
        "Syncs Xbox game saves.",
        "disabled",
        "You use Xbox cloud saves.",
    ),
    StartupService(
        "XboxNetApiSvc",
        "Xbox Live Networking",
        "Xbox Live network helper.",
        "disabled",
        "You play Xbox / Game Pass games online.",
    ),
    StartupService(
        "XboxGipSvc",
        "Xbox Accessory Management",
        "Xbox controller and accessory helper.",
        "disabled",
        "You use an Xbox controller.",
    ),
    StartupService(
        "GamingServices",
        "Gaming Services",
        "Game Bar / gaming install helper. Often resident after sign-in.",
        "disabled",
        "You use Game Bar, Xbox, or Game Pass.",
    ),
    StartupService(
        "GamingServicesNet",
        "Gaming Services Network",
        "Networking side of Gaming Services.",
        "disabled",
        "You use Game Bar, Xbox, or Game Pass.",
    ),
    StartupService(
        "GameInputSvc",
        "GameInput",
        "Game controller input service.",
        "disabled",
        "Games or controllers stop working after you disable it.",
    ),
    StartupService(
        "WMPNetworkSvc",
        "Windows Media Player Network Sharing",
        "Legacy media-library sharing (DLNA).",
        "disabled",
        "Other devices stream from Windows Media Player on this PC.",
    ),
    StartupService(
        "RemoteAccess",
        "Routing and Remote Access",
        "Incoming RRAS routing. This is not the VPN client.",
        "disabled",
        "This PC is a dial-in / RRAS router.",
    ),
    StartupService(
        "WalletService",
        "Wallet Service",
        "Legacy Wallet payments service.",
        "disabled",
        "An old app still depends on Windows Wallet.",
    ),
    StartupService(
        "wisvc",
        "Windows Insider Service",
        "Insider preview flighting.",
        "disabled",
        "This PC is on the Windows Insider program.",
    ),
    StartupService(
        "WpcMonSvc",
        "Parental Controls",
        "Family Safety monitoring service.",
        "disabled",
        "You use Microsoft Family Safety on this PC.",
    ),
    StartupService(
        "AJRouter",
        "AllJoyn Router",
        "Unused IoT discovery protocol on typical PCs.",
        "disabled",
        "You use AllJoyn devices.",
    ),
    StartupService(
        "AssignedAccessManagerSvc",
        "Assigned Access Manager",
        "Kiosk / assigned-access mode.",
        "disabled",
        "This PC is a kiosk.",
    ),
    StartupService(
        "shpamsvc",
        "Shared PC Account Manager",
        "Shared-PC mode used by schools.",
        "disabled",
        "This PC uses Windows Shared PC mode.",
    ),
    StartupService(
        "spectrum",
        "Windows Perception Service",
        "Mixed Reality spatial perception.",
        "disabled",
        "You use a Mixed Reality headset.",
    ),
    StartupService(
        "perceptionsimulation",
        "Windows Perception Simulation",
        "Mixed Reality simulation (dev / headset).",
        "disabled",
        "You develop for or use Mixed Reality.",
    ),
    StartupService(
        "MixedRealityOpenXRSvc",
        "Windows Mixed Reality OpenXR",
        "OpenXR runtime for VR headsets.",
        "disabled",
        "You use a VR / Mixed Reality headset.",
    ),
    StartupService(
        "SEMgrSvc",
        "Payments and NFC / Secure Element",
        "NFC tap-to-pay stack.",
        "disabled",
        "You use NFC payments on this PC.",
    ),
    StartupService(
        "pla",
        "Performance Logs & Alerts",
        "Manual performance traces. Not needed at startup.",
        "disabled",
        "You record performance counters with this service.",
    ),
    StartupService(
        "InventorySvc",
        "Inventory and Compatibility Appraisal",
        "App-compatibility inventory. Telemetry-adjacent.",
        "disabled",
        "You rely on Program Compatibility inventory.",
    ),
    StartupService(
        "SharedAccess",
        "Internet Connection Sharing",
        "Shares this PC's connection with other devices (ICS).",
        "disabled",
        "This PC shares its internet connection.",
    ),
    StartupService(
        "BcastDVRUserService",
        "Game DVR and Broadcast User Service",
        "Background Game DVR user service.",
        "disabled",
        "You record gameplay with Game Bar.",
        True,
    ),
    StartupService(
        "MessagingService",
        "Messaging Service",
        "Legacy messaging / SMS user service.",
        "disabled",
        "You use a messaging app that depends on this service.",
        True,
    ),
    StartupService(
        "Spooler",
        "Print Spooler",
        "Print queue. Automatic on most PCs even when you never print.",
        "demand",
        "You print. Uncheck this row if you do — Manual still lets Windows start it when you print, but test a page after Clean.",
    ),
    StartupService(
        "PrintNotify",
        "Printer Extensions and Notifications",
        "Printer toast / extension helper.",
        "demand",
        "You want printer status toasts.",
    ),
    StartupService(
        "icssvc",
        "Windows Mobile Hotspot",
        "Mobile hotspot host.",
        "demand",
        "You use the mobile hotspot feature.",
    ),
    StartupService(
        "PhoneSvc",
        "Phone Service",
        "Telephony helper used by Phone Link calling.",
        "demand",
        "You use Phone Link calls.",
    ),
    StartupService(
        "TabletInputService",
        "Touch Keyboard and Handwriting",
        "On-screen keyboard and pen input. Idle RAM on desktops without touch.",
        "demand",
        "This is a tablet or touchscreen and you use the touch keyboard.",
    ),
    StartupService(
        "lfsvc",
        "Geolocation Service",
        "Location provider for Maps, weather, and Find My Device.",
        "demand",
        "You want location available as soon as you sign in.",
    ),
    StartupService(
        "TrkWks",
        "Distributed Link Tracking Client",
        "Tracks shortcuts to files moved on NTFS. Rarely useful at home.",
        "demand",
        "You depend on cross-volume shortcut repair.",
    ),
    StartupService(
        "CscService",
        "Offline Files",
        "Corporate offline-files cache.",
        "demand",
        "This PC uses Offline Files or folder redirection.",
    ),
    StartupService(
        "diagnosticshub.standardcollector.service",
        "Diagnostics Hub Standard Collector",
        "Visual Studio / diagnostics collector.",
        "demand",
        "You profile apps with Visual Studio.",
    ),
    StartupService(
        "DPS",
        "Diagnostic Policy Service",
        "Built-in troubleshooters. Safe to leave stopped until you run one.",
        "demand",
        "You want troubleshooters available without a manual start.",
    ),
    StartupService(
        "WdiServiceHost",
        "Diagnostic Service Host",
        "Diagnostic host process.",
        "demand",
        "You want diagnostic scenarios running at startup.",
    ),
    StartupService(
        "WdiSystemHost",
        "Diagnostic System Host",
        "System diagnostic host.",
        "demand",
        "You want diagnostic scenarios running at startup.",
    ),
    StartupService(
        "SCardSvr",
        "Smart Card",
        "Smart-card logon.",
        "demand",
        "You sign in with a smart card.",
    ),
    StartupService(
        "SCPolicySvc",
        "Smart Card Removal Policy",
        "Locks the PC when a smart card is removed.",
        "demand",
        "You use smart-card removal lock.",
    ),
    StartupService(
        "ScDeviceEnum",
        "Smart Card Device Enumeration",
        "Enumerates smart-card readers.",
        "demand",
        "You use a smart card.",
    ),
    StartupService(
        "FrameServer",
        "Windows Camera Frame Server",
        "Webcam frame sharing. Apps can start it when the camera opens.",
        "demand",
        "A camera app fails to open after this change.",
    ),
    StartupService(
        "stisvc",
        "Windows Image Acquisition (WIA)",
        "Scanners and some cameras.",
        "demand",
        "You scan from this PC.",
    ),
    StartupService(
        "fdPHost",
        "Function Discovery Provider Host",
        "Network device discovery (printers, media).",
        "demand",
        "Network printer / device discovery feels broken.",
    ),
    StartupService(
        "FDResPub",
        "Function Discovery Resource Publication",
        "Publishes this PC so other devices can discover it.",
        "demand",
        "Other PCs must discover this one on the LAN.",
    ),
    StartupService(
        "SSDPSRV",
        "SSDP Discovery",
        "UPnP device discovery.",
        "demand",
        "UPnP discovery is required on your network.",
    ),
    StartupService(
        "upnphost",
        "UPnP Device Host",
        "Hosts UPnP devices.",
        "demand",
        "You host UPnP devices.",
    ),
    StartupService(
        "lmhosts",
        "TCP/IP NetBIOS Helper",
        "Old NetBIOS name lookups.",
        "demand",
        "Old network shares stop resolving by name.",
    ),
    StartupService(
        "LanmanServer",
        "Server (file and printer sharing)",
        "Lets other PCs open shared folders on this PC.",
        "demand",
        "Other computers open shared folders or printers on this PC.",
    ),
    StartupService(
        "TermService",
        "Remote Desktop Services",
        "Incoming Remote Desktop listener.",
        "demand",
        "You connect to this PC with Remote Desktop.",
    ),
    StartupService(
        "SessionEnv",
        "Remote Desktop Configuration",
        "Remote Desktop session setup.",
        "demand",
        "You connect to this PC with Remote Desktop.",
    ),
    StartupService(
        "UmRdpService",
        "Remote Desktop Port Redirector",
        "Remote Desktop device redirection.",
        "demand",
        "You connect to this PC with Remote Desktop.",
    ),
    StartupService(
        "seclogon",
        "Secondary Logon",
        "Run as a different user.",
        "demand",
        "You use Run as different user.",
    ),
    StartupService(
        "ShellHWDetection",
        "Shell Hardware Detection",
        "AutoPlay when you plug in a drive.",
        "demand",
        "You want AutoPlay immediately.",
    ),
    StartupService(
        "iphlpsvc",
        "IP Helper",
        "IPv6 transition technologies. Some VPNs use it.",
        "demand",
        "A VPN or IPv6 tunnel stops working.",
    ),
    StartupService(
        "DusmSvc",
        "Data Usage",
        "Network data-usage tracking.",
        "demand",
        "You use Settings data-usage counters.",
    ),
    StartupService(
        "workfolders",
        "Work Folders",
        "Enterprise Work Folders sync.",
        "demand",
        "You use Work Folders.",
    ),
    StartupService(
        "fhsvc",
        "File History Service",
        "File History backup.",
        "demand",
        "You use File History.",
    ),
    StartupService(
        "CaptureService",
        "Capture Service",
        "Screen capture user service (Snipping Tool / Game Bar).",
        "demand",
        "Win+Shift+S or Game Bar capture stops working.",
        True,
    ),
    StartupService(
        "cbdhsvc",
        "Clipboard User Service",
        "Clipboard history user service (Win+V).",
        "demand",
        "You use clipboard history.",
        True,
    ),
    StartupService(
        "CDPUserSvc",
        "Connected Devices Platform User Service",
        "Phone Link, Nearby sharing, and some device features.",
        "demand",
        "You use Phone Link or Nearby sharing.",
        True,
    ),
    StartupService(
        "OneSyncSvc",
        "Sync Host",
        "Settings / account sync user service.",
        "demand",
        "You rely on settings sync across PCs.",
        True,
    ),
    StartupService(
        "PimIndexMaintenanceSvc",
        "Contact Data",
        "Indexes contacts for search.",
        "demand",
        "Contact search in Windows feels broken.",
        True,
    ),
    StartupService(
        "UnistoreSvc",
        "User Data Storage",
        "User-data store used by Mail, People, and some Store apps.",
        "demand",
        "Mail, People, or a Store app misbehaves.",
        True,
    ),
    StartupService(
        "UserDataSvc",
        "User Data Access",
        "User-data access used with Mail and People.",
        "demand",
        "Mail, People, or a Store app misbehaves.",
        True,
    ),
]


def should_offer(start: str | None, state: str | None, target: str) -> bool:
    """True when the service is set to start with Windows, or is already in memory.

    Boot and system drivers are never offered. Demand-target rows are only
    offered when startup is Automatic — already-manual services stay as they are
    so features can still start them on use.
    """
    if not start:
        return False
    upper = start.upper()
    if "DISABLED" in upper or "BOOT" in upper or "SYSTEM_START" in upper:
        return False
    auto = "AUTO" in upper
    running = bool(state) and "RUNNING" in state.upper()
    if target == "disabled":
        return auto or running
    if target == "demand":
        return auto
    return False


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


def _service_state(name: str) -> tuple[str | None, str | None]:
    proc = _run(["sc", "qc", name])
    if proc.returncode != 0:
        return None, None
    start = None
    for line in proc.stdout.splitlines():
        if "START_TYPE" in line.upper():
            parts = line.split(":", 1)
            if len(parts) == 2:
                start = parts[1].strip()
    proc2 = _run(["sc", "query", name])
    state = None
    if proc2.returncode == 0:
        for line in proc2.stdout.splitlines():
            if "STATE" in line.upper() and ":" in line:
                state = line.split(":", 1)[1].strip()
    return start, state


def _user_service_names() -> list[str]:
    proc = _run(["sc", "query", "type=", "userservice", "state=", "all"])
    if proc.returncode != 0:
        return []
    names: list[str] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("SERVICE_NAME:"):
            name = stripped.split(":", 1)[1].strip()
            if name:
                names.append(name)
    return names


def _instances_for(prefix: str) -> list[tuple[str, str | None, str | None]]:
    found: list[tuple[str, str | None, str | None]] = []
    for name in _user_service_names():
        if name == prefix or name.startswith(prefix + "_"):
            start, state = _service_state(name)
            found.append((name, start, state))
    return found


def _interesting(
    rows: list[tuple[str, str | None, str | None]], target: str
) -> list[tuple[str, str | None, str | None]]:
    return [row for row in rows if should_offer(row[1], row[2], target)]


def _apply_start(name: str, target: str) -> tuple[int, str]:
    mode = "disabled" if target == "disabled" else "demand"
    _run(["sc", "stop", name])
    cfg = _run(["sc", "config", name, "start=", mode])
    err = (cfg.stderr or "").strip() or (cfg.stdout or "").strip()
    return cfg.returncode, err


class StartupServicesModule(CleanModule):
    id = "startup_services"
    label = "Optional Startup Services"
    description = (
        "Stops Windows services that are not required on a typical PC and either "
        "auto-start or are already sitting in memory (Fax, Xbox/Game Bar, Game DVR, "
        "print spooler, Remote Desktop listener, Phone Link helpers, and similar). "
        "Does not touch Defender, Windows Update, firewall, audio, Wi-Fi, Bluetooth, "
        "or Windows Hello. Uncheck any row you still use. SysMain and Windows Search "
        "stay in Optional Performance Services."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for svc in SERVICES:
            if progress:
                progress(f"Checking service {svc.name}")
            if svc.per_user:
                rows = _interesting(_instances_for(svc.name), svc.target)
                if not rows:
                    template_start, template_state = _service_state(svc.name)
                    if should_offer(template_start, template_state, svc.target):
                        rows = [(svc.name, template_start, template_state)]
                if not rows:
                    continue
                current = "; ".join(
                    f"{name}: {start or '?'} / {state or '?'}" for name, start, state in rows[:2]
                )
                if len(rows) > 2:
                    current += f" (+{len(rows) - 2} more)"
            else:
                start, state = _service_state(svc.name)
                if not should_offer(start, state, svc.target):
                    continue
                current = f"{start}; {state}"

            if svc.target == "disabled":
                effect = f"Sets {svc.label} to Disabled and stops it."
                action = "Disabled — it will not start until you turn it back on."
            else:
                effect = (
                    f"Sets {svc.label} to Manual and stops it now so it is not resident after boot."
                )
                action = "Manual — Windows can still start it when a feature asks."
            result.items.append(
                CleanItem(
                    id=f"{'usvc' if svc.per_user else 'svc'}:{svc.name}",
                    label=f"Service: {svc.label}",
                    detail=f"{svc.name} — {svc.reason} (current: {current})",
                    bytes_estimate=0,
                    requires_admin=True,
                    effect=effect,
                    repercussions=f"{action} Keep this service if: {svc.keep_if} Re-enable in services.msc.",
                )
            )
        return result

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        result = self.scan(progress)
        result.items = filter_items(result.items, only_ids)
        result.dry_run = dry_run
        admin = is_admin()
        by_name = {svc.name: svc for svc in SERVICES}

        for item in result.items:
            if progress:
                progress(f"{'Would change' if dry_run else 'Changing'} {item.label}")
            if not dry_run and not admin:
                item.detail = "Needs Administrator - not applied (will show again on Scan)"
                item.repercussions = "Run Restart as Administrator, then Clean again."
                result.errors.append(f"{item.id}: needs Administrator")
                continue
            name = item.id.split(":", 1)[1]
            svc = by_name.get(name)
            if svc is None:
                result.errors.append(f"{item.id}: unknown service")
                continue
            mode_word = "disable" if svc.target == "disabled" else "set to Manual"
            names = [name]
            if svc.per_user:
                names = [inst for inst, _, _ in _instances_for(name)]
                if name not in names:
                    names.insert(0, name)
            if dry_run:
                result.actions.append(f"Would {mode_word} {', '.join(names)}")
                continue
            ok = 0
            failures: list[str] = []
            for target_name in names:
                code, err = _apply_start(target_name, svc.target)
                if code == 0:
                    ok += 1
                elif code == 1060:
                    continue
                else:
                    failures.append(f"{target_name}: {err or 'failed'}")
            if ok and not failures:
                result.actions.append(f"{mode_word.capitalize()} {name}")
            elif ok and failures:
                result.actions.append(f"{mode_word.capitalize()} {name} (partial)")
                result.errors.append(f"{item.id}: {'; '.join(failures)}")
            else:
                err = "; ".join(failures) or "service was not changed"
                item.detail = err
                result.errors.append(f"{item.id}: {err}")
        return result
