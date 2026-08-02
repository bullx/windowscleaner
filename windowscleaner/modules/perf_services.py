"""Optional performance services (SysMain / WSearch) — aggressive, never default-on."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk


@dataclass(frozen=True)
class PerfService:
    name: str
    label: str
    reason: str


SERVICES: list[PerfService] = [
    PerfService(
        "SysMain",
        "SysMain (Superfetch)",
        "Prefetches apps into RAM. Disabling can reduce disk thrash on HDDs / low RAM; "
        "on SSDs with free RAM it may make cold app launches slightly slower.",
    ),
    PerfService(
        "WSearch",
        "Windows Search Indexer",
        "Background file indexing. Disabling reduces disk/CPU idle work but hurts "
        "Start menu and Explorer search quality until re-enabled.",
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


class PerfServicesModule(CleanModule):
    id = "perf_services"
    label = "Optional Performance Services"
    description = (
        "Optionally disables SysMain (Superfetch) and/or Windows Search indexer. "
        "Helps some PCs, hurts others — review repercussions. Never enabled in "
        "Safe/Standard/Privacy presets; Full includes it only if you leave it checked."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False

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
                    detail=f"{svc.name} — {svc.reason} (current: {start}; {state})",
                    bytes_estimate=0,
                    requires_admin=True,
                    effect=f"Sets {svc.name} startup type to Disabled and stops it if running.",
                    repercussions=svc.reason + " Re-enable anytime in services.msc.",
                )
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        result = self.scan(progress)
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
            name = item.id.split(":", 1)[1]
            if dry_run:
                result.actions.append(f"Would disable service {name}")
                continue
            _run(["sc", "stop", name])
            cfg = _run(["sc", "config", name, "start=", "disabled"])
            if cfg.returncode == 0:
                result.actions.append(f"Disabled service {name}")
            else:
                err = cfg.stderr.strip() or cfg.stdout.strip() or "failed"
                item.detail = err
                result.errors.append(f"{item.id}: {err}")
        return result
