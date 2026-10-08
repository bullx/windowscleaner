"""Smoke tests — no live system mutation."""

from __future__ import annotations

from windowscleaner import __version__
from windowscleaner.cleaner import select_modules
from windowscleaner.modules import OPT_IN_MODULE_IDS, all_modules, module_by_id
from windowscleaner.modules.base import Risk, allow_item, filter_items, CleanItem
from windowscleaner.utils.registry import values_match
from windowscleaner.utils.report_export import report_to_dict
from windowscleaner.cleaner import CleanReport
from windowscleaner.modules.base import ModuleResult


def test_version_semver_shape() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])


def test_all_modules_unique_ids() -> None:
    ids = [m.id for m in all_modules()]
    assert len(ids) == len(set(ids))
    assert "startup_apps" in ids
    assert "privacy" in ids


def test_opt_in_modules_default_off() -> None:
    for mid in OPT_IN_MODULE_IDS:
        mod = module_by_id(mid)
        assert mod is not None
        assert mod.default_enabled is False


def test_select_modules_profiles() -> None:
    safe = {m.id for m in select_modules(profile="safe")}
    assert safe
    assert all(module_by_id(i).risk == Risk.SAFE for i in safe)  # type: ignore[union-attr]

    standard = {m.id for m in select_modules(profile="standard")}
    assert "privacy" in standard
    assert "bloatware" not in standard
    assert "startup_apps" not in standard
    assert "perf_services" not in standard
    assert "startup_services" not in standard

    privacy = {m.id for m in select_modules(profile="privacy")}
    assert privacy == {"privacy", "tracking", "telemetry_services"}

    oem = {m.id for m in select_modules(profile="oem")}
    assert oem == {"bloatware", "bloatware_oem"}

    disk = {m.id for m in select_modules(profile="disk")}
    assert "temp_files" in disk and "caches" in disk
    assert "privacy" not in disk

    new_pc = {m.id for m in select_modules(profile="new_pc")}
    assert "bloatware_oem" in new_pc and "privacy" in new_pc
    assert "startup_services" not in new_pc

    debloat = {m.id for m in select_modules(profile="debloat")}
    assert debloat == {"bloatware", "bloatware_oem", "startup_services"}

    full = {m.id for m in select_modules(profile="full")}
    assert "bloatware" in full
    assert "startup_apps" in full
    assert "perf_services" not in full
    assert "startup_services" not in full


def test_startup_services_catalog_is_safe() -> None:
    from windowscleaner.modules.perf_services import SERVICES as PERF
    from windowscleaner.modules.startup_services import SERVICES, should_offer
    from windowscleaner.modules.telemetry_services import SERVICES as TELEMETRY

    names = [svc.name for svc in SERVICES]
    assert len(names) == len(set(names))
    assert set(names).isdisjoint({svc.name for svc in TELEMETRY})
    assert set(names).isdisjoint({svc.name for svc in PERF})

    never = {
        "WinDefend",
        "WdNisSvc",
        "MDCoreSvc",
        "SecurityHealthService",
        "wscsvc",
        "Sense",
        "mpssvc",
        "BFE",
        "wuauserv",
        "UsoSvc",
        "WaaSMedicSvc",
        "BITS",
        "DoSvc",
        "edgeupdate",
        "CryptSvc",
        "SamSs",
        "RpcSs",
        "DcomLaunch",
        "LSM",
        "EventLog",
        "Schedule",
        "Dhcp",
        "Dnscache",
        "Audiosrv",
        "AudioEndpointBuilder",
        "WlanSvc",
        "bthserv",
        "BthAvctpSvc",
        "NgcSvc",
        "NgcCtnrSvc",
        "WbioSrvc",
        "vmcompute",
        "HvHost",
        "hns",
        "LxssManager",
        "AppXSvc",
        "ClipSVC",
        "sppsvc",
        "webthreatdefsvc",
        "webthreatdefusersvc",
        "wlidsvc",
        "SysMain",
        "WSearch",
        "DiagTrack",
    }
    assert set(names).isdisjoint(never)
    assert all(svc.target in {"disabled", "demand"} for svc in SERVICES)

    assert should_offer("2   AUTO_START", "4  RUNNING", "disabled")
    assert should_offer("2   AUTO_START (DELAYED)", "1  STOPPED", "demand")
    assert not should_offer("4   DISABLED", "1  STOPPED", "disabled")
    assert not should_offer("3   DEMAND_START", "1  STOPPED", "disabled")
    assert should_offer("3   DEMAND_START", "4  RUNNING", "disabled")
    assert not should_offer("3   DEMAND_START", "4  RUNNING", "demand")
    assert not should_offer("0   BOOT_START", "4  RUNNING", "disabled")
    assert not should_offer("1   SYSTEM_START", "4  RUNNING", "demand")
    assert not should_offer(None, None, "disabled")


def test_bloat_includes_inbox_optional_apps() -> None:
    from windowscleaner.modules.bloatware import BLOAT

    matches = {app.match for app in BLOAT}
    for needle in (
        "Microsoft.WindowsCamera",
        "Microsoft.MicrosoftMinesweeper",
        "Microsoft.Windows.NarratorQuickStart",
        "Clipchamp.Clipchamp",
    ):
        assert needle in matches


def test_allow_item_and_filter() -> None:
    assert allow_item("a", None) is True
    assert allow_item("a", {"a", "b"}) is True
    assert allow_item("c", {"a"}) is False
    items = [
        CleanItem(id="a", label="A", detail=""),
        CleanItem(id="b", label="B", detail=""),
    ]
    assert [i.id for i in filter_items(items, {"b"})] == ["b"]
    assert len(filter_items(items, None)) == 2


def test_values_match() -> None:
    assert values_match(0, 0)
    assert values_match("1", 1)
    assert not values_match(None, 0)
    assert not values_match(1, 0)


def test_report_to_dict_shape() -> None:
    report = CleanReport(admin=False)
    report.results.append(
        ModuleResult(
            module_id="temp_files",
            label="Temporary Files",
            items=[CleanItem(id="user_temp", label="Temp", detail="x", bytes_estimate=10)],
        )
    )
    data = report_to_dict(report, mode="scan")
    assert data["mode"] == "scan"
    assert data["version"] == __version__
    assert data["modules"][0]["items"][0]["id"] == "user_temp"
