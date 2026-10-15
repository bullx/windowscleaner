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
    assert debloat == {"bloatware", "bloatware_oem", "startup_services", "windows_features"}

    full = {m.id for m in select_modules(profile="full")}
    assert "bloatware" in full
    assert "startup_apps" in full
    assert "ai_caches" in full
    assert "dev_caches" in full
    assert "app_caches" in full
    assert "perf_services" not in full
    assert "startup_services" not in full
    assert "ai_history" not in full
    assert "ai_models" not in full
    assert "system_reclaim" not in full
    assert "driver_store" not in full
    assert "dev_disks" not in full
    assert "windows_features" not in full

    disk = {m.id for m in select_modules(profile="disk")}
    assert "temp_files" in disk and "caches" in disk
    assert "ai_caches" in disk and "dev_caches" in disk and "app_caches" in disk
    assert "privacy" not in disk
    assert "ai_history" not in disk and "ai_models" not in disk and "dev_disks" not in disk

    workstation = {m.id for m in select_modules(profile="workstation")}
    assert workstation == disk

    ai = {m.id for m in select_modules(profile="ai")}
    assert ai == {"ai_caches", "ai_history"}

    standard_again = {m.id for m in select_modules(profile="standard")}
    assert "ai_caches" not in standard_again
    assert "ai_history" not in standard_again
    assert "system_reclaim" not in standard_again


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


def _isolate_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "Temp"))
    for key in (
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "COPILOT_HOME",
        "COPILOT_CACHE_HOME",
        "CLAUDE_CODE_TMPDIR",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "Roaming").mkdir()
    (tmp_path / "Local").mkdir()
    (tmp_path / "Temp").mkdir()


def test_ai_modules_exist_and_empty_home_shows_nothing(tmp_path, monkeypatch) -> None:
    from windowscleaner.modules.ai_caches import AiCachesModule
    from windowscleaner.modules.ai_history import AiHistoryModule
    from windowscleaner.modules.ai_models import AiModelsModule

    _isolate_home(monkeypatch, tmp_path)
    assert AiCachesModule().scan().items == []
    assert AiHistoryModule().scan().items == []
    assert AiModelsModule().scan().items == []


def test_ai_allowlist_skips_secrets_and_dry_run_keeps_files(tmp_path, monkeypatch) -> None:
    from windowscleaner.modules.ai_caches import AiCachesModule
    from windowscleaner.modules.ai_history import AiHistoryModule
    from windowscleaner.modules.ai_models import AiModelsModule
    from windowscleaner.modules.ai_targets import all_delete_paths

    _isolate_home(monkeypatch, tmp_path)
    roaming = tmp_path / "Roaming"
    home = tmp_path
    cache = roaming / "Cursor" / "Cache"
    cache.mkdir(parents=True)
    (cache / "a.bin").write_bytes(b"xyz")
    settings = roaming / "Cursor" / "User" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}", encoding="utf-8")
    (roaming / "Cursor" / "auth.json").write_text("secret", encoding="utf-8")
    skills = home / ".cursor" / "skills"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("keep", encoding="utf-8")
    claude = home / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("{}", encoding="utf-8")
    (claude / ".credentials.json").write_text("secret", encoding="utf-8")
    (claude / "cache").mkdir()
    (claude / "cache" / "x").write_bytes(b"1")
    (home / ".claude.json").write_text("{}", encoding="utf-8")
    project = claude / "projects" / "demo"
    (project / "memory").mkdir(parents=True)
    (project / "memory" / "note.md").write_text("keep", encoding="utf-8")
    (project / "chat.jsonl").write_text("bye", encoding="utf-8")
    models = home / ".ollama" / "models"
    models.mkdir(parents=True)
    (models / "blob").write_bytes(b"weight")
    (home / ".ollama" / "id_ed25519").write_text("key", encoding="utf-8")

    paths = all_delete_paths()
    blob = "\n".join(str(p) for p in paths).lower()
    assert "program files" not in blob
    for banned in ("auth.json", ".credentials.json", "settings.json", "id_ed25519"):
        assert banned not in blob
    assert not any(part.lower() == "skills" for path in paths for part in path.parts)
    assert (project / "memory" / "note.md").exists()
    assert not any("memory" in path.parts and path.name == "note.md" for path in paths)

    caches = AiCachesModule()
    dry = caches.clean(dry_run=True)
    assert dry.dry_run
    assert (cache / "a.bin").exists()
    assert any(item.id == "cursor_roaming_cache" for item in dry.items)

    caches.clean(dry_run=False)
    assert not cache.exists()
    assert settings.exists()
    assert skills.exists()
    assert (claude / "settings.json").exists()
    assert (claude / ".credentials.json").exists()
    assert (home / ".claude.json").exists()

    history = AiHistoryModule().clean(dry_run=False)
    assert any(item.id == "claude_sessions" for item in history.items)
    assert not (project / "chat.jsonl").exists()
    assert (project / "memory" / "note.md").exists()

    models_mod = AiModelsModule()
    assert all(item.default_include is False for item in models_mod.scan().items)
    models_mod.clean(dry_run=False)
    assert (models / "blob").exists()
    models_mod.clean(dry_run=False, only_ids={"ollama_models"})
    assert not (models / "blob").exists()
    assert (home / ".ollama" / "id_ed25519").exists()


def test_browser_and_app_caches_leave_logins(tmp_path, monkeypatch) -> None:
    from windowscleaner.modules.app_caches import app_cache_plans
    from windowscleaner.modules.browser_caches import browser_cache_plans

    _isolate_home(monkeypatch, tmp_path)
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    edge = local / "Microsoft" / "Edge" / "User Data" / "Profile 1"
    (edge / "Cache").mkdir(parents=True)
    (edge / "Cache" / "x").write_bytes(b"1")
    (edge / "Cookies").write_bytes(b"cookie")
    (edge / "History").write_bytes(b"hist")
    discord = roaming / "discord"
    (discord / "Cache").mkdir(parents=True)
    (discord / "Cache" / "x").write_bytes(b"1")
    (discord / "Local Storage").mkdir()
    (discord / "IndexedDB").mkdir()

    cache_paths = [path for plan in browser_cache_plans() for path in plan.paths]
    assert cache_paths
    assert all(path.name.lower() not in {"cookies", "history", "login data", "web data"} for path in cache_paths)

    app_paths = [path for plan in app_cache_plans() for path in plan.paths]
    assert any(path.name == "Cache" for path in app_paths)
    assert all(path.name.lower() not in {"local storage", "indexeddb"} for path in app_paths)
    assert all("common" not in {part.lower() for part in path.parts} for path in app_paths)


def test_dev_cache_plans_skip_project_trees(tmp_path, monkeypatch) -> None:
    from windowscleaner.modules.dev_caches import dev_cache_plans

    _isolate_home(monkeypatch, tmp_path)
    local = tmp_path / "Local"
    npm = local / "npm-cache"
    npm.mkdir(parents=True)
    (npm / "x").write_bytes(b"1")
    cargo_git = tmp_path / ".cargo" / "git"
    cargo_git.mkdir(parents=True)
    (cargo_git / "db").write_bytes(b"1")
    registry = tmp_path / ".cargo" / "registry"
    registry.mkdir()
    (registry / "src").write_bytes(b"1")
    packages = tmp_path / ".nuget" / "packages"
    packages.mkdir(parents=True)
    (packages / "lib").write_bytes(b"1")

    paths = [path for plan in dev_cache_plans() for path in plan.paths]
    blob = [str(path).lower() for path in paths]
    assert any("npm-cache" in item for item in blob)
    assert any(item.endswith(".cargo\\git") or item.endswith(".cargo/git") for item in blob)
    assert not any(item.rstrip("\\/").endswith("registry") for item in blob)
    assert not any("node_modules" in item for item in blob)
    assert not any(".nuget" in item and item.rstrip("\\/").endswith("packages") for item in blob)


def test_driver_store_skips_in_use_packages() -> None:
    from windowscleaner.modules.driver_store import (
        in_use_published_names,
        parse_enum_drivers,
        superseded_packages,
    )

    listed = """
Published Name:     oem1.inf
Original Name:      net.inf
Provider Name:      Intel
Class Name:         Net
Driver Version:     01/02/2020 1.0.0.0

Published Name:     oem2.inf
Original Name:      audio.inf
Provider Name:      Realtek
Class Name:         MEDIA
Driver Version:     03/03/2021 2.0.0.0

Published Name:     prnms001.inf
Original Name:      inbox.inf
Provider Name:      Microsoft
Class Name:         Printer
Driver Version:     01/01/2019 1.0.0.0
"""
    devices = "Instance ID: PCI\\VEN\nDriver Name: oem2.inf\n"
    packages = parse_enum_drivers(listed)
    chosen = superseded_packages(packages, in_use_published_names(devices))
    published = {pkg.published.lower() for pkg in chosen}
    assert published == {"oem1.inf"}


def test_system_reclaim_dry_run_does_not_mutate(monkeypatch) -> None:
    from subprocess import CompletedProcess

    from windowscleaner.modules import system_reclaim

    calls: list[list[str]] = []

    def fake_run(cmd, timeout=None):
        calls.append(list(cmd))
        text = " ".join(cmd)
        if "AnalyzeComponentStore" in text:
            stdout = "Backups and Disabled Features : 2.00 GB\nCache and Temporary Data : 512.00 MB\n"
            return CompletedProcess(cmd, 0, stdout=stdout, stderr="")
        if "vssadmin" in text and "list" in text:
            stdout = (
                "Used Shadow Copy Storage space: 8.00 GB (4%)\n"
                "Maximum Shadow Copy Storage space: UNBOUNDED\n"
            )
            return CompletedProcess(cmd, 0, stdout=stdout, stderr="")
        if cmd[:1] == ["powercfg"]:
            return CompletedProcess(cmd, 0, stdout="Hibernate\n", stderr="")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(system_reclaim, "run_hidden", fake_run)
    monkeypatch.setattr(system_reclaim, "hiberfil_path", lambda: system_reclaim.Path("Z:/missing-hiberfil.sys"))
    monkeypatch.setattr(system_reclaim, "upgrade_paths", lambda: [])
    result = system_reclaim.SystemReclaimModule().clean(dry_run=True)
    scanned = system_reclaim.SystemReclaimModule().scan()
    assert result.dry_run
    assert any(item.id == "component_store" and item.bytes_estimate > 0 for item in result.items)
    assert all(item.id != "component_store_resetbase" for item in result.items)
    assert any(item.id == "component_store_resetbase" and item.default_include is False for item in scanned.items)
    flat = [" ".join(cmd) for cmd in calls]
    assert not any("StartComponentCleanup" in cmd for cmd in flat)
    assert not any("-h" in cmd and "off" in cmd for cmd in flat)
    assert "ResetBase" not in system_reclaim.cleanup_command(resetbase=False)[-1]
    assert system_reclaim.cleanup_command(resetbase=True)[-1] == "/ResetBase"
    resize = system_reclaim.shadow_resize_command(8 * 1024**3)
    assert "delete" not in " ".join(resize).lower()


def test_windows_features_keeps_current_language() -> None:
    from windowscleaner.modules.windows_features import selectable_names

    names = [
        "Language.Basic~~~en-US~0.0.1.0",
        "Language.Basic~~~fr-FR~0.0.1.0",
        "XPS.Viewer~~~~0.0.1.0",
        "App.StepsRecorder~~~~0.0.1.0",
        "Media.WindowsMediaPlayer~~~~0.0.12.0",
        "SMB1Protocol",
        "NetFx3",
        "Microsoft-Hyper-V-All",
        "Printing-XPSServices-Features",
    ]
    chosen = {item_id for item_id, _label, _kind in selectable_names(names, {"en-US"})}
    assert "capability:Language.Basic~~~en-US~0.0.1.0" not in chosen
    assert "capability:Language.Basic~~~fr-FR~0.0.1.0" in chosen
    assert any(item.startswith("capability:XPS.Viewer") for item in chosen)
    assert not any("Hyper-V" in item or "SMB1" in item or "NetFx" in item for item in chosen)


def test_schedule_command_is_disk_profile() -> None:
    from windowscleaner.utils.schedule_disk import disk_clean_command

    command = disk_clean_command()
    assert "--profile disk" in command
    assert "ai_models" not in command


def test_normalize_service_start() -> None:
    from windowscleaner.utils.change_undo import normalize_start

    assert normalize_start("2   AUTO_START") == "auto"
    assert normalize_start("2   AUTO_START (DELAYED)") == "delayed-auto"
    assert normalize_start("3   DEMAND_START") == "demand"
    assert normalize_start("4   DISABLED") == "disabled"

