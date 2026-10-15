"""Cleanup module registry."""

from __future__ import annotations

from windowscleaner.modules.ai_caches import AiCachesModule
from windowscleaner.modules.ai_history import AiHistoryModule
from windowscleaner.modules.ai_models import AiModelsModule
from windowscleaner.modules.app_caches import AppCachesModule
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
from windowscleaner.modules.browser_privacy import BrowserPrivacyModule
from windowscleaner.modules.caches import CachesModule
from windowscleaner.modules.dev_caches import DevCachesModule
from windowscleaner.modules.dev_disks import DevDisksModule
from windowscleaner.modules.driver_store import DriverStoreModule
from windowscleaner.modules.gpu_caches import GpuCachesModule
from windowscleaner.modules.logs import LogsModule
from windowscleaner.modules.network_cache import NetworkCacheModule
from windowscleaner.modules.perf_services import PerfServicesModule
from windowscleaner.modules.privacy import PrivacyModule
from windowscleaner.modules.recycle_bin import RecycleBinModule
from windowscleaner.modules.startup_apps import StartupAppsModule
from windowscleaner.modules.startup_services import StartupServicesModule
from windowscleaner.modules.system_reclaim import SystemReclaimModule
from windowscleaner.modules.telemetry_services import TelemetryServicesModule
from windowscleaner.modules.temp_files import TempFilesModule
from windowscleaner.modules.tracking import TrackingModule
from windowscleaner.modules.windows_features import WindowsFeaturesModule

__all__ = [
    "CleanItem",
    "CleanModule",
    "ModuleResult",
    "ProgressCb",
    "Risk",
    "all_modules",
    "module_by_id",
]

# Modules that must never auto-enable in standard (opt-in aggressive / selective)
OPT_IN_MODULE_IDS = frozenset(
    {
        "bloatware",
        "bloatware_oem",
        "perf_services",
        "startup_apps",
        "startup_services",
        "ai_caches",
        "ai_history",
        "ai_models",
        "browser_privacy",
        "system_reclaim",
        "driver_store",
        "dev_disks",
        "windows_features",
    }
)

# Opt-in modules that stay unchecked even in the Full preset.
# Debloat turns startup_services and windows_features on explicitly.
# AI chats, model weights, system reclaim, old drivers, and WSL/Docker stay manual.
MANUAL_PRESET_IDS = frozenset(
    {
        "perf_services",
        "startup_services",
        "ai_history",
        "ai_models",
        "system_reclaim",
        "driver_store",
        "dev_disks",
        "windows_features",
    }
)


def all_modules() -> list[CleanModule]:
    return [
        TempFilesModule(),
        RecycleBinModule(),
        BrowserCachesModule(),
        BrowserPrivacyModule(),
        GpuCachesModule(),
        CachesModule(),
        AppCachesModule(),
        DevCachesModule(),
        LogsModule(),
        TrackingModule(),
        NetworkCacheModule(),
        PrivacyModule(),
        TelemetryServicesModule(),
        StartupAppsModule(),
        BloatwareModule(),
        BloatwareOemModule(),
        StartupServicesModule(),
        PerfServicesModule(),
        AiCachesModule(),
        AiHistoryModule(),
        AiModelsModule(),
        DevDisksModule(),
        SystemReclaimModule(),
        DriverStoreModule(),
        WindowsFeaturesModule(),
    ]


def module_by_id(module_id: str) -> CleanModule | None:
    for m in all_modules():
        if m.id == module_id:
            return m
    return None
