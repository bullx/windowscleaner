"""Export Scan/Clean reports for support / undo audit."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from windowscleaner import __app_name__, __version__
from windowscleaner.cleaner import CleanReport
from windowscleaner.utils.size import format_bytes
from windowscleaner.utils.windows_info import windows_edition


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WindowsCleaner"
    base.mkdir(parents=True, exist_ok=True)
    return base


def report_to_dict(report: CleanReport, *, mode: str) -> dict[str, Any]:
    counts = getattr(report, "verify_counts", None) or {}
    return {
        "app": __app_name__,
        "version": __version__,
        "mode": mode,
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "admin": report.admin,
        "dry_run": report.dry_run,
        "edition": windows_edition(),
        "bytes_estimate": report.bytes_estimate,
        "bytes_freed": report.bytes_freed,
        "verify_counts": dict(counts),
        "skipped_modules": list(report.skipped_modules),
        "modules": [
            {
                "id": r.module_id,
                "label": r.label,
                "bytes_estimate": r.bytes_estimate,
                "bytes_freed": r.bytes_freed,
                "actions": list(r.actions),
                "errors": list(r.errors),
                "items": [
                    {
                        "id": i.id,
                        "label": i.label,
                        "status": i.status,
                        "next_step": i.next_step,
                        "detail": i.detail,
                        "effect": i.effect,
                        "repercussions": i.repercussions,
                        "bytes_estimate": i.bytes_estimate,
                        "requires_admin": i.requires_admin,
                        "risk": i.risk,
                    }
                    for i in r.items
                ],
            }
            for r in report.results
        ],
    }


def report_to_text(report: CleanReport, *, mode: str) -> str:
    data = report_to_dict(report, mode=mode)
    lines = [
        f"{data['app']} v{data['version']} — {mode} report",
        f"When: {data['when']}",
        f"Edition: {data['edition'] or 'unknown'}",
        f"Administrator: {'yes' if data['admin'] else 'no'}",
        f"Dry-run: {'yes' if data['dry_run'] else 'no'}",
        f"Estimate: {format_bytes(data['bytes_estimate'])} · Freed: {format_bytes(data['bytes_freed'])}",
    ]
    if data["verify_counts"]:
        vc = ", ".join(f"{k}={v}" for k, v in sorted(data["verify_counts"].items()))
        lines.append(f"Verify: {vc}")
    if data["skipped_modules"]:
        lines.append("Admin-blocked modules: " + "; ".join(data["skipped_modules"]))
    lines.append("")
    for mod in data["modules"]:
        if not mod["items"] and not mod["actions"] and not mod["errors"]:
            continue
        lines.append(f"## {mod['label']} ({mod['id']})")
        for item in mod["items"]:
            lines.append(
                f"  [{item.get('status') or '-'}] {item['label']} "
                f"({format_bytes(item['bytes_estimate'])}) — {item.get('detail') or ''}"
            )
            if item.get("next_step"):
                lines.append(f"    What to do: {item['next_step']}")
        for a in mod["actions"]:
            lines.append(f"  action: {a}")
        for e in mod["errors"]:
            lines.append(f"  error: {e}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_report(
    report: CleanReport,
    *,
    mode: str,
    path: Path | None = None,
    as_json: bool = True,
) -> Path:
    """Write report to path (or default under LocalAppData). Returns path written."""
    if path is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        ext = "json" if as_json else "txt"
        path = app_data_dir() / f"report-{mode}-{stamp}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_json or path.suffix.lower() == ".json":
        path.write_text(
            json.dumps(report_to_dict(report, mode=mode), indent=2),
            encoding="utf-8",
        )
    else:
        path.write_text(report_to_text(report, mode=mode), encoding="utf-8")
    # Also keep a stable "last" copy for support
    last = app_data_dir() / ("last_report.json" if path.suffix.lower() == ".json" else "last_report.txt")
    try:
        if path.suffix.lower() == ".json":
            last.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            last.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass
    return path
