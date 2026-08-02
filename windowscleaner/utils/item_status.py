"""Item status + next-step logic, last-clean history, and post-clean verification."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from windowscleaner.modules.base import CleanItem, ModuleResult
from windowscleaner.utils.admin import is_admin

# ephemeral  = expected to refill (caches/temps)
# sticky     = should stay gone if apply succeeded (privacy/services/bloat)
# maintenance = always runnable again (DNS)
MODULE_KIND: dict[str, str] = {
    "temp_files": "ephemeral",
    "recycle_bin": "ephemeral",
    "browser_caches": "ephemeral",
    "gpu_caches": "ephemeral",
    "caches": "ephemeral",
    "logs": "ephemeral",
    "tracking": "ephemeral",
    "network_cache": "maintenance",
    "privacy": "sticky",
    "telemetry_services": "sticky",
    "bloatware": "sticky",
    "bloatware_oem": "sticky",
    "perf_services": "sticky",
}

# Modules where nearly every fix needs elevation (sticky policy / services / uninstall)
ADMIN_MODULES = {
    "privacy",
    "telemetry_services",
    "bloatware",
    "bloatware_oem",
    "perf_services",
}

# Statuses that mean "do not override with verify Fixed unless gone"
_FAIL_STATUSES = {
    "Failed",
    "Failed — Needs Admin",
    "Needs Admin",
    "Dry-run",
}


def history_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WindowsCleaner"
    base.mkdir(parents=True, exist_ok=True)
    return base / "last_clean.json"


def item_key(module_id: str, item_id: str) -> str:
    return f"{module_id}::{item_id}"


def load_history() -> dict[str, Any]:
    path = history_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("items"), dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "when": 0, "admin": False, "items": {}, "skipped_modules": []}


def save_history(data: dict[str, Any]) -> None:
    try:
        history_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def _errors_for_item(item: CleanItem, errors: list[str]) -> list[str]:
    """Errors that belong to this item (avoid short-label false positives)."""
    iid = (item.id or "").lower()
    if not iid:
        return []
    prefix = f"{iid}:"
    bare = iid.split(":", 1)[-1].lower() if ":" in iid else ""
    detail = (item.detail or "").lower()
    detail_is_path = detail.startswith(("c:\\", "d:\\", "e:\\", "%", "/"))
    matched: list[str] = []
    for err in errors:
        el = err.lower()
        if el.startswith(prefix) or f" {prefix}" in f" {el}":
            matched.append(err)
            continue
        if iid in el and (
            el.startswith(iid)
            or f"{iid}:" in el
            or f"({iid})" in el
            or f" {iid} " in f" {el} "
        ):
            matched.append(err)
            continue
        if bare and len(bare) >= 4 and (
            el.startswith(f"{bare}:")
            or f"service {bare}" in el
            or f"task {bare}" in el
            or f" {bare}:" in f" {el}"
        ):
            matched.append(err)
            continue
        # Child-file lock errors under this folder path
        if detail_is_path and detail in el:
            matched.append(err)
    return matched


def _error_matches_item(item: CleanItem, errors: list[str]) -> bool:
    return bool(_errors_for_item(item, errors))


def _looks_admin_failure(text: str) -> bool:
    t = text.lower()
    return any(
        s in t
        for s in (
            "needs administrator",
            "access is denied",
            "access denied",
            "denied",
            "privilege",
            "elevat",
        )
    )


def annotate_scan_result(result: ModuleResult, history: dict[str, Any] | None = None) -> ModuleResult:
    history = history if history is not None else load_history()
    hist_items: dict[str, Any] = history.get("items") or {}
    admin = is_admin()
    kind = MODULE_KIND.get(result.module_id, "ephemeral")
    skipped_mods = set(history.get("skipped_modules") or [])
    module_skipped = result.module_id in skipped_mods or bool(
        hist_items.get(item_key(result.module_id, "__module_skipped__"))
    )

    for item in result.items:
        _annotate_scan_item(
            result.module_id,
            item,
            kind=kind,
            hist=hist_items.get(item_key(result.module_id, item.id)),
            admin=admin,
            module_skipped=module_skipped,
        )
    return result


def annotate_clean_result(result: ModuleResult, *, dry_run: bool, admin: bool) -> ModuleResult:
    """Initial clean labels — verify_clean_results() may upgrade to Fixed / Not fixed."""
    kind = MODULE_KIND.get(result.module_id, "ephemeral")

    for item in result.items:
        detail_l = (item.detail or "").lower()
        reper_l = (item.repercussions or "").lower()
        item_errors = _errors_for_item(item, result.errors)
        matched_err = bool(item_errors)
        admin_fail = _looks_admin_failure(item.detail or "") or any(
            _looks_admin_failure(e) for e in item_errors
        )
        blocked_no_admin = bool(item.requires_admin and not admin and not dry_run)
        failed = (
            blocked_no_admin
            or "needs administrator" in detail_l
            or "write failed" in detail_l
            or "will keep appearing" in reper_l
            or "skipped (needs administrator)" in detail_l
            or matched_err
        )
        needs_admin = blocked_no_admin or admin_fail or "needs administrator" in detail_l

        if dry_run:
            item.status = "Dry-run"
            item.next_step = "Run Clean to apply"
            continue

        if failed:
            item.status = "Failed — Needs Admin" if needs_admin else "Failed"
            item.next_step = (
                "Restart as Administrator → Clean"
                if needs_admin
                else "Retry Clean (close locking apps / reboot if needed)"
            )
            continue

        if kind == "ephemeral":
            item.status = "Cleaned"
            item.next_step = "Verifying…"
        elif kind == "sticky":
            item.status = "Applied"
            item.next_step = "Verifying…"
        else:
            item.status = "Done"
            item.next_step = "Verifying…"

    return result


def verify_clean_results(
    clean_results: list[ModuleResult],
    verified_by_module: dict[str, ModuleResult],
    *,
    admin: bool,
) -> dict[str, int]:
    """
    Re-check Scan after Clean. Status becomes the product truth:
      Fixed        — cleaned/applied and no longer detected
      Not fixed    — sticky item still detected
      Still present— file/cache target still has content (locked/partial)
      Failed — Needs Admin — left as-is (or upgraded to Fixed if somehow gone)
    Returns counts for UI summary.
    """
    counts: dict[str, int] = {}

    for result in clean_results:
        kind = MODULE_KIND.get(result.module_id, "ephemeral")
        follow = verified_by_module.get(result.module_id)
        remaining = {i.id for i in follow.items} if follow else set()

        for item in result.items:
            gone = item.id not in remaining

            if item.status in _FAIL_STATUSES or (item.status or "").startswith("Failed"):
                if gone:
                    item.status = "Fixed"
                    item.next_step = "Verified — no longer detected"
                elif "Admin" not in (item.status or "") and kind != "sticky":
                    # Locked / partial file clean — say Still present after re-check
                    item.status = "Still present"
                    item.next_step = (
                        "Still on disk — close apps / reboot, or Clean again"
                    )
                # else keep Failed — Needs Admin / sticky failure
            elif gone:
                item.status = "Fixed"
                if kind == "sticky":
                    item.next_step = "Verified fixed — should stay off"
                elif kind == "maintenance":
                    item.next_step = "Verified done — safe to run again anytime"
                else:
                    item.next_step = "Verified cleared (may refill later — normal)"
            else:
                # Still detected after Clean
                if kind == "sticky":
                    item.status = "Not fixed"
                    item.next_step = (
                        "Still detected — Restart as Administrator → Clean"
                        if not admin
                        else "Still detected — retry Clean or reboot"
                    )
                elif kind == "maintenance":
                    item.status = "Done"
                    item.next_step = "Flush ran — cache refills while browsing (normal)"
                else:
                    item.status = "Still present"
                    item.next_step = (
                        "Still on disk — close apps / reboot, or Clean again "
                        "(Needs Admin if path is system-protected)"
                    )

            counts[item.status or "?"] = counts.get(item.status or "?", 0) + 1

    return counts


def record_clean_report(
    results: list[ModuleResult],
    *,
    dry_run: bool,
    admin: bool,
    skipped_modules: list[str],
    module_ids_skipped: list[str] | None = None,
) -> None:
    """Persist what Clean tried + verified, so the next Scan can explain reappearing items."""
    if dry_run:
        return

    prev = load_history()
    items: dict[str, Any] = dict(prev.get("items") or {})
    now = time.time()

    for result in results:
        kind = MODULE_KIND.get(result.module_id, "ephemeral")
        for item in result.items:
            key = item_key(result.module_id, item.id)
            status = item.status or ""
            status_l = status.lower()

            if status in {"Fixed", "Cleaned", "Applied", "Done"} or status_l.startswith("cleaned"):
                items[key] = {
                    "ok": True,
                    "module_id": result.module_id,
                    "item_id": item.id,
                    "label": item.label,
                    "kind": kind,
                    "reason": "verified" if status == "Fixed" else "applied",
                    "when": now,
                    "status": status,
                }
            elif status in {"Still present"} and kind == "ephemeral":
                # Partial / locked — not a successful clear
                items[key] = {
                    "ok": False,
                    "module_id": result.module_id,
                    "item_id": item.id,
                    "label": item.label,
                    "kind": kind,
                    "reason": "partial",
                    "when": now,
                    "status": status,
                }
            else:
                needs_admin = (
                    "admin" in status_l
                    or item.requires_admin
                    or result.module_id in ADMIN_MODULES
                )
                items[key] = {
                    "ok": False,
                    "module_id": result.module_id,
                    "item_id": item.id,
                    "label": item.label,
                    "kind": kind,
                    "reason": "needs_admin" if (needs_admin and not admin) else "failed",
                    "when": now,
                    "status": status,
                }

    skipped_ids = list(module_ids_skipped or [])
    for mid in skipped_ids:
        kind = MODULE_KIND.get(mid, "ephemeral")
        items[item_key(mid, "__module_skipped__")] = {
            "ok": False,
            "module_id": mid,
            "item_id": "__module_skipped__",
            "kind": kind,
            "reason": "needs_admin",
            "when": now,
        }

    save_history(
        {
            "version": 1,
            "when": now,
            "admin": admin,
            "skipped": list(skipped_modules),
            "skipped_modules": skipped_ids,
            "items": items,
        }
    )


def _annotate_scan_item(
    module_id: str,
    item: CleanItem,
    *,
    kind: str,
    hist: dict[str, Any] | None,
    admin: bool,
    module_skipped: bool,
) -> None:
    needs_elevation = (
        (item.requires_admin and not admin)
        or (module_id in ADMIN_MODULES and not admin)
        or (module_skipped and not admin)
    )

    # History first for precise "Came back" / "Still open"
    if hist:
        if hist.get("ok"):
            if kind == "ephemeral":
                item.status = "Came back"
                item.next_step = "Normal refill — Clean again only if you want more space"
                return
            if kind == "sticky":
                item.status = "Still open"
                item.next_step = "Did not stick — Restart as Administrator → Clean"
                return
            item.status = "Ready again"
            item.next_step = "Optional — Clean anytime"
            return
        if hist.get("reason") == "needs_admin" or needs_elevation:
            item.status = "Needs Admin"
            item.next_step = "Restart as Administrator → Clean"
            return
        if hist.get("reason") == "partial":
            item.status = "Still present"
            item.next_step = "Close locking apps / reboot, then Clean again"
            return
        item.status = "Failed before"
        item.next_step = "Retry Clean (as Administrator if required)"
        return

    if needs_elevation:
        item.status = "Needs Admin"
        item.next_step = "Restart as Administrator → Clean (or it will keep showing)"
        return

    if kind == "sticky":
        item.status = "Ready"
        item.next_step = "Clean to apply — should stay off after success"
        return

    if kind == "maintenance":
        item.status = "Ready"
        item.next_step = "Optional flush — safe anytime"
        return

    item.status = "Ready"
    item.next_step = "Clean to free space (may refill later — normal)"
