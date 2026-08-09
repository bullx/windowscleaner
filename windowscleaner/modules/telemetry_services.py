"""Disable noisy telemetry-related services and scheduled tasks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item, filter_items


@dataclass(frozen=True)
class ServiceTarget:
    name: str
    label: str
    reason: str


@dataclass(frozen=True)
class TaskTarget:
    path: str
    label: str
    reason: str


# Services commonly tied to telemetry / customer experience. We set startup
# type to Disabled - we do NOT delete the service binaries.
SERVICES: list[ServiceTarget] = [
    ServiceTarget(
        "DiagTrack",
        "Connected User Experiences and Telemetry",
        "Primary Windows telemetry pipeline.",
    ),
    ServiceTarget(
        "dmwappushservice",
        "WAP Push Message Routing Service",
        "Device management push channel often unused on desktops.",
    ),
    ServiceTarget(
        "WerSvc",
        "Windows Error Reporting Service",
        "Uploads crash reports; optional if you don't need WER.",
    ),
    ServiceTarget(
        "PcaSvc",
        "Program Compatibility Assistant",
        "Tracks app compatibility; rarely useful on modern apps.",
    ),
    ServiceTarget(
        "RetailDemo",
        "Retail Demo Service",
        "Store demo mode - never needed on personal PCs.",
    ),
    ServiceTarget(
        "RemoteRegistry",
        "Remote Registry",
        "Allows remote registry access; attack surface.",
    ),
    ServiceTarget(
        "MapsBroker",
        "Downloaded Maps Manager",
        "WinUtil often sets this Manual; unused without offline maps.",
    ),
    ServiceTarget(
        "WSAIFabricSvc",
        "Windows AI Fabric / AI service",
        "Win11Debloat: AI fabric service auto-start (if present).",
    ),
]

TASKS: list[TaskTarget] = [
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
        "Compatibility Appraiser",
        "Inventory telemetry for Microsoft.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\ProgramDataUpdater",
        "ProgramDataUpdater",
        "Compatibility telemetry updater.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\StartupAppTask",
        "StartupAppTask",
        "Startup app telemetry.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
        "CEIP Consolidator",
        "Customer Experience Improvement Program.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
        "USB CEIP",
        "USB device CEIP telemetry.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
        "Disk Diagnostic Data Collector",
        "Disk diagnostic telemetry.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Feedback\Siuf\DmClient",
        "Feedback DmClient",
        "Feedback / SIUF client.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload",
        "Feedback DmClientOnScenarioDownload",
        "Feedback scenario downloader.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Windows Error Reporting\QueueReporting",
        "WER QueueReporting",
        "Queued error report uploader.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Autochk\Proxy",
        "Autochk Proxy",
        "CEIP-related autochk proxy.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\PI\Sqm-Tasks",
        "SQM Tasks",
        "Software Quality Metrics.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\NetTrace\GatherNetworkInfo",
        "GatherNetworkInfo",
        "Network info collection task.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\CloudExperienceHost\CreateObjectTask",
        "CloudExperienceHost CreateObjectTask",
        "Cloud experience host maintenance.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\PcaPatchDbTask",
        "PcaPatchDbTask",
        "Compatibility assistant DB task (Sophia / community lists).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Device Information\Device",
        "Device Information Device",
        "Device info telemetry upload.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Device Information\Device User",
        "Device Information Device User",
        "Per-user device info telemetry.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Diagnosis\Scheduled",
        "Diagnosis Scheduled",
        "Scheduled diagnostic collection.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Maps\MapsToastTask",
        "Maps Toast Task",
        "Maps notifications / telemetry.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Maps\MapsUpdateTask",
        "Maps Update Task",
        "Offline maps updater (unused if you don't use Maps).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Flighting\FeatureConfig\ReconcileFeatures",
        "Flighting ReconcileFeatures",
        "Windows Insider / flighting feature reconcile.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Flighting\FeatureConfig\UsageDataFlushing",
        "Flighting UsageDataFlushing",
        "Flighting usage data flush.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Flighting\FeatureConfig\UsageDataReporting",
        "Flighting UsageDataReporting",
        "Flighting usage data reporting.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\PushToInstall\LoginCheck",
        "PushToInstall LoginCheck",
        "Silent Store app push on login.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\PushToInstall\Registration",
        "PushToInstall Registration",
        "Silent Store app push registration.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Shell\FamilySafetyMonitor",
        "FamilySafetyMonitor",
        "Family Safety monitor task.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Shell\FamilySafetyRefreshTask",
        "FamilySafetyRefreshTask",
        "Family Safety refresh.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\AitAgent",
        "AitAgent",
        "Application Impact Telemetry agent (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Application Experience\MareBackup",
        "MareBackup",
        "Application Experience MareBackup telemetry (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Power Efficiency Diagnostics\AnalyzeSystem",
        "Power Efficiency AnalyzeSystem",
        "Power efficiency diagnostic upload task.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticResolver",
        "Disk Diagnostic Resolver",
        "Disk diagnostic resolver (optional; keep if you use disk troubleshooting).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Maintenance\WinSAT",
        "WinSAT",
        "Windows System Assessment Tool scheduled run.",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Diagnosis\RecommendedTroubleshootingScanner",
        "Recommended Troubleshooting Scanner",
        "Recommended troubleshooting scanner telemetry (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Input\LocalUserSyncDataAvailable",
        "LocalUserSyncDataAvailable",
        "Input personalization sync signal task (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Input\MouseSyncDataAvailable",
        "MouseSyncDataAvailable",
        "Mouse sync data task (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Input\PenSyncDataAvailable",
        "PenSyncDataAvailable",
        "Pen sync data task (if present).",
    ),
    TaskTarget(
        r"\Microsoft\Windows\Input\TouchpadSyncDataAvailable",
        "TouchpadSyncDataAvailable",
        "Touchpad sync data task (if present).",
    ),
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


def _service_state(name: str) -> tuple[str | None, str | None]:
    """Return (start_type, state) or (None, None) if missing."""
    proc = _run(["sc", "qc", name])
    if proc.returncode != 0:
        return None, None
    start = None
    for line in proc.stdout.splitlines():
        if "START_TYPE" in line.upper():
            # e.g. START_TYPE         : 2   AUTO_START
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


def _task_enabled(path: str) -> bool | None:
    proc = _run(["schtasks", "/Query", "/TN", path, "/FO", "LIST", "/V"])
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.strip().lower().startswith("scheduled task state"):
            val = line.split(":", 1)[-1].strip().lower()
            return val == "enabled"
        if line.strip().lower().startswith("status"):
            # LIST without /V sometimes only has Status
            pass
    # Fallback: present but unknown -> treat as enabled to offer disable
    return True


class TelemetryServicesModule(CleanModule):
    id = "telemetry_services"
    label = "Telemetry Services & Tasks"
    description = (
        "Disables DiagTrack and related services, plus CEIP / Compatibility / "
        "Feedback scheduled tasks. Reversible via services.msc / Task Scheduler."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)

        for svc in SERVICES:
            if progress:
                progress(f"Checking service {svc.name}")
            start, state = _service_state(svc.name)
            if start is None:
                continue
            if "DISABLED" in start.upper():
                continue
            result.items.append(
                CleanItem(
                    id=f"svc:{svc.name}",
                    label=f"Service: {svc.label}",
                    detail=f"{svc.name} - {svc.reason} (current: {start}; {state})",
                    bytes_estimate=0,
                    requires_admin=True,
                )
            )

        for task in TASKS:
            if progress:
                progress(f"Checking task {task.label}")
            enabled = _task_enabled(task.path)
            if enabled is None:
                continue
            if not enabled:
                continue
            result.items.append(
                CleanItem(
                    id=f"task:{task.path}",
                    label=f"Task: {task.label}",
                    detail=f"{task.path} - {task.reason}",
                    bytes_estimate=0,
                    requires_admin=True,
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

        for item in result.items:
            if progress:
                progress(f"{'Would disable' if dry_run else 'Disabling'} {item.label}")

            if not dry_run and not admin:
                item.detail = "Needs Administrator - not applied (will show again on Scan)"
                item.repercussions = "Run Restart as Administrator, then Clean again."
                result.errors.append(f"{item.id}: needs Administrator")
                continue

            if item.id.startswith("svc:"):
                name = item.id.split(":", 1)[1]
                if dry_run:
                    result.actions.append(f"Would disable service {name}")
                    continue
                stop = _run(["sc", "stop", name])
                cfg = _run(["sc", "config", name, "start=", "disabled"])
                if cfg.returncode == 0:
                    result.actions.append(f"Disabled service {name}")
                else:
                    err = cfg.stderr.strip() or cfg.stdout.strip() or "failed"
                    item.detail = err
                    result.errors.append(f"{item.id}: {err}")
                if stop.returncode not in (0, 1060, 1062):
                    # 1062 = not started; ignore
                    pass

            elif item.id.startswith("task:"):
                path = item.id.split(":", 1)[1]
                if dry_run:
                    result.actions.append(f"Would disable task {path}")
                    continue
                proc = _run(["schtasks", "/Change", "/TN", path, "/Disable"])
                if proc.returncode == 0:
                    result.actions.append(f"Disabled task {path}")
                else:
                    err = proc.stderr.strip() or proc.stdout.strip() or "failed"
                    item.detail = err
                    result.errors.append(f"{item.id}: {err}")

        return result
