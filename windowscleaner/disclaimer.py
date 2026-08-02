"""User-facing disclaimer text (keep README / GUI / CLI in sync)."""

from __future__ import annotations

DISCLAIMER_SHORT = (
    "Use at your own risk. Scan and Dry-run first. Create a restore point before Clean. "
    "Bloatware/OEM removal and some privacy tweaks are hard to undo. "
    "Not affiliated with Microsoft."
)

DISCLAIMER_FULL = """\
DISCLAIMER — read before using Windows Cleaner

This software is provided “as is”, without warranty of any kind, express or implied.
You use it at your own risk. The authors and distributors are not liable for data loss,
broken apps, lost OEM utilities, failed rollbacks, or any other damage.

What this tool can do
  • Delete temporary files, caches, logs, Recycle Bin contents, and (if present) Windows.old
  • Change privacy / AI / telemetry registry and policy settings
  • Disable services and scheduled tasks
  • Uninstall Store (AppX) apps and deprovision them for new users
  • Optionally uninstall OEM / Win32 software via winget
  • Optionally disable SysMain or Windows Search (can help or hurt performance)

Important limits
  • Not every “slow PC” cause is covered. Telemetry and bloat help some systems; others
    need driver fixes, free disk space, or fewer startup apps.
  • Windows Home may still send Required diagnostic data even when telemetry policies are set.
  • OEM tools (SupportAssist, HP Wolf, Lenovo Vantage, AV trials) may reinstall via
    drivers, BIOS, or Windows Update. McAfee/Norton often need the vendor removal tool.
  • App uninstalls are irreversible without reinstalling from the Microsoft Store (or OEM).
  • Deleting Windows.old permanently removes the previous Windows install / rollback.
  • Disabling WSearch hurts Start/file search; disabling SysMain can slow cold launches on SSDs.

Safety habits
  1. Prefer Scan → Dry-run → Clean
  2. Enable “Create System Restore point” before Clean (when available)
  3. Run as Administrator only when you need privacy / services / system / bloat changes
  4. Review Aggressive modules (bloatware, OEM, perf services) item-by-item before Clean
  5. This tool does NOT disable Windows Defender or Windows Update, and does not touch
     BitLocker, disk partitions, or WinRE

Affiliation
  Not affiliated with, endorsed by, or sponsored by Microsoft Corporation or any PC OEM.
  Methods use documented Windows APIs, folders, registry policies, services, Task Scheduler,
  PowerShell AppX, and winget — aligned with public community tools (Win11Debloat, WinUtil,
  ShutUp10-style guides). No exploits.

By clicking Clean (or confirming in the CLI) you acknowledge that you understand these risks
and accept full responsibility for changes made to your system.
"""
