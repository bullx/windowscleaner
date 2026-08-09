"""Best-effort Windows edition / product info (shared by privacy + GUI)."""

from __future__ import annotations

import winreg


def windows_edition() -> str:
    """ProductName such as 'Windows 11 Home' (empty string on failure)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        ) as key:
            name, _ = winreg.QueryValueEx(key, "ProductName")
            return str(name)
    except OSError:
        return ""


def is_windows_home() -> bool:
    return "home" in windows_edition().lower()


def edition_banner_text() -> str:
    """One-line honesty banner for the GUI / CLI."""
    edition = windows_edition() or "Windows (edition unknown)"
    if is_windows_home():
        return (
            f"{edition}: Required diagnostic data may still apply even after privacy policies. "
            "Privacy Clean still writes the keys; do not expect fully-off telemetry on Home."
        )
    return (
        f"{edition}: Privacy policies can cap telemetry more tightly than Home. "
        "Security/required data may still apply by Microsoft policy."
    )


def telemetry_edition_note(setting_id: str) -> str:
    if setting_id not in {"telemetry_level", "telemetry_dual", "max_telemetry_allowed"}:
        return ""
    if is_windows_home():
        return (
            " Note: on Windows Home, Microsoft may still enforce Required diagnostic "
            "data even when this policy is 0 — Scan/Clean still apply the key."
        )
    return ""
