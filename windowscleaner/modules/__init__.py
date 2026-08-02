"""Cleanup module registry."""

from __future__ import annotations

from windowscleaner.modules.base import (
    CleanItem,
    CleanModule,
    ModuleResult,
    ProgressCb,
    Risk,
)
from windowscleaner.modules.bloatware import BloatwareModule
from windowscleaner.modules.bloatware_oem import BloatwareOemModule
from windowscleaner.modules.browser_caches import BrowserCachesModule
from windowscleaner.modules.caches import CachesModule
from windowscleaner.modules.gpu_caches import GpuCachesModule
from windowscleaner.modules.logs import LogsModule
from windowscleaner.modules.network_cache import NetworkCacheModule
from windowscleaner.modules.perf_services import PerfServicesModule
from windowscleaner.modules.privacy import PrivacyModule
from windowscleaner.modules.recycle_bin import RecycleBinModule
from windowscleaner.modules.telemetry_services import TelemetryServicesModule
from windowscleaner.modules.temp_files import TempFilesModule
from windowscleaner.modules.tracking import TrackingModule

__all__ = [
    "CleanItem",
    "CleanModule",
    "ModuleResult",
    "ProgressCb",
    "Risk",
    "all_modules",
    "module_by_id",
]

# Modules that must never auto-enable in standard (opt-in aggressive)
OPT_IN_MODULE_IDS = frozenset({"bloatware", "bloatware_oem", "perf_services"})


def all_modules() -> list[CleanModule]:
    return [
        TempFilesModule(),
        RecycleBinModule(),
        BrowserCachesModule(),
        GpuCachesModule(),
        CachesModule(),
        LogsModule(),
        TrackingModule(),
        NetworkCacheModule(),
        PrivacyModule(),
        TelemetryServicesModule(),
        BloatwareModule(),
        BloatwareOemModule(),
        PerfServicesModule(),
    ]


def module_by_id(module_id: str) -> CleanModule | None:
    for m in all_modules():
        if m.id == module_id:
            return m
    return None
