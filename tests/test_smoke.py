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

    privacy = {m.id for m in select_modules(profile="privacy")}
    assert privacy == {"privacy", "tracking", "telemetry_services"}

    oem = {m.id for m in select_modules(profile="oem")}
    assert oem == {"bloatware", "bloatware_oem"}

    disk = {m.id for m in select_modules(profile="disk")}
    assert "temp_files" in disk and "caches" in disk
    assert "privacy" not in disk

    new_pc = {m.id for m in select_modules(profile="new_pc")}
    assert "bloatware_oem" in new_pc and "privacy" in new_pc

    full = {m.id for m in select_modules(profile="full")}
    assert "bloatware" in full
    assert "startup_apps" in full
    assert "perf_services" not in full


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
