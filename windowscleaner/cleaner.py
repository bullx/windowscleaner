"""Orchestrates scan and clean across selected modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from windowscleaner.modules import all_modules
from windowscleaner.modules.base import CleanModule, ModuleResult, ProgressCb, Risk
from windowscleaner.modules.item_info import enrich_result
from windowscleaner.utils.admin import is_admin
from windowscleaner.utils.item_status import (
    annotate_clean_result,
    annotate_scan_result,
    load_history,
    record_clean_report,
    verify_clean_results,
)


@dataclass
class CleanReport:
    results: list[ModuleResult] = field(default_factory=list)
    dry_run: bool = False
    admin: bool = False
    skipped_modules: list[str] = field(default_factory=list)
    skipped_module_ids: list[str] = field(default_factory=list)
    verify_counts: dict[str, int] = field(default_factory=dict)

    @property
    def bytes_estimate(self) -> int:
        return sum(r.bytes_estimate for r in self.results)

    @property
    def bytes_freed(self) -> int:
        return sum(r.bytes_freed for r in self.results)

    @property
    def action_count(self) -> int:
        return sum(len(r.actions) for r in self.results)

    @property
    def error_count(self) -> int:
        return sum(len(r.errors) for r in self.results)

    @property
    def item_count(self) -> int:
        return sum(len(r.items) for r in self.results)


def select_modules(
    *,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
    profile: str = "standard",
) -> list[CleanModule]:
    """
    Profiles:
      safe      - SAFE risk only
      standard  - default modules (space + privacy + telemetry services; no bloat/OEM/perf)
      privacy   - privacy hardening + tracking wipe + telemetry services/tasks
      oem       - bloatware AppX + OEM/winget module only
      full      - everything except optional perf_services (SysMain/WSearch stay manual)
    """
    from windowscleaner.modules import OPT_IN_MODULE_IDS

    only_set = {x.strip() for x in (only or []) if x.strip()}
    exclude_set = {x.strip() for x in (exclude or []) if x.strip()}
    selected: list[CleanModule] = []

    for mod in all_modules():
        if only_set:
            if mod.id in only_set and mod.id not in exclude_set:
                selected.append(mod)
            continue

        if mod.id in exclude_set:
            continue

        if profile == "safe":
            if mod.risk == Risk.SAFE and mod.default_enabled:
                selected.append(mod)
        elif profile == "privacy":
            if mod.id in {"privacy", "tracking", "telemetry_services"}:
                selected.append(mod)
        elif profile == "oem":
            if mod.id in {"bloatware", "bloatware_oem"}:
                selected.append(mod)
        elif profile == "full":
            # Include bloatware + OEM; leave controversial perf services unchecked
            if mod.id != "perf_services":
                selected.append(mod)
        else:  # standard
            if mod.id in OPT_IN_MODULE_IDS:
                continue
            if mod.default_enabled:
                selected.append(mod)

    return selected


class Cleaner:
    def __init__(self, modules: list[CleanModule]):
        self.modules = modules

    def scan(self, progress: ProgressCb | None = None) -> CleanReport:
        report = CleanReport(admin=is_admin())
        history = load_history()
        for mod in self.modules:
            if progress:
                progress(f"Scanning: {mod.label}")
            try:
                result = enrich_result(mod.scan(progress))
                annotate_scan_result(result, history)
                report.results.append(result)
            except Exception as e:
                failed = ModuleResult(module_id=mod.id, label=mod.label)
                failed.errors.append(str(e))
                report.results.append(failed)
        return report

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> CleanReport:
        report = CleanReport(dry_run=dry_run, admin=is_admin())
        cleaned_mods: list[CleanModule] = []

        for mod in self.modules:
            if progress:
                progress(f"{'Dry-run' if dry_run else 'Cleaning'}: {mod.label}")
            try:
                result = enrich_result(mod.clean(dry_run=dry_run, progress=progress))
                annotate_clean_result(result, dry_run=dry_run, admin=report.admin)
                report.results.append(result)
                cleaned_mods.append(mod)

                # Track modules that could not apply anything without Admin
                if (
                    not dry_run
                    and not report.admin
                    and mod.requires_admin
                    and result.items
                    and all(
                        (i.status or "").startswith("Failed") or i.status == "Needs Admin"
                        for i in result.items
                    )
                ):
                    report.skipped_modules.append(f"{mod.label} (needs Administrator)")
                    report.skipped_module_ids.append(mod.id)
            except Exception as e:
                failed = ModuleResult(module_id=mod.id, label=mod.label, dry_run=dry_run)
                failed.errors.append(str(e))
                report.results.append(failed)

        if not dry_run and cleaned_mods:
            if progress:
                progress("Verifying fixes (re-scan)...")
            verified: dict[str, ModuleResult] = {}
            for mod in cleaned_mods:
                if progress:
                    progress(f"Verifying: {mod.label}")
                try:
                    verified[mod.id] = enrich_result(mod.scan(progress))
                except Exception as e:
                    empty = ModuleResult(module_id=mod.id, label=mod.label)
                    empty.errors.append(f"verify failed: {e}")
                    verified[mod.id] = empty

            report.verify_counts = verify_clean_results(
                report.results,
                verified,
                admin=report.admin,
            )
            record_clean_report(
                report.results,
                dry_run=False,
                admin=report.admin,
                skipped_modules=report.skipped_modules,
                module_ids_skipped=report.skipped_module_ids,
            )
        elif not dry_run:
            record_clean_report(
                report.results,
                dry_run=False,
                admin=report.admin,
                skipped_modules=report.skipped_modules,
                module_ids_skipped=report.skipped_module_ids,
            )

        return report
