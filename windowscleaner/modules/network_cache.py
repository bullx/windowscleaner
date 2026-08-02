"""DNS cache flush - maintenance action, not persistent junk."""

from __future__ import annotations

import subprocess

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk


class NetworkCacheModule(CleanModule):
    id = "network_cache"
    label = "DNS / Network Cache"
    description = (
        "Flushes the DNS resolver cache (ipconfig /flushdns). "
        "This is a maintenance action - it will always be available to run again "
        "because DNS entries refill as you browse."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        # Do not pretend there is reclaimable disk junk every scan.
        # DNS cache size is not usefully measurable; listing it every time
        # made users think cleanup "didn't work".
        result = ModuleResult(module_id=self.id, label=self.label)
        if progress:
            progress("DNS cache is a flush action (not sized junk)")
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label, dry_run=dry_run)
        result.items.append(
            CleanItem(
                id="flushdns",
                label="DNS resolver cache",
                detail="ipconfig /flushdns (refills as you browse)",
                bytes_estimate=0,
            )
        )
        if dry_run:
            result.actions.append("Would flush DNS cache")
            return result
        if progress:
            progress("Flushing DNS cache...")
        proc = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode == 0:
            result.actions.append("Flushed DNS resolver cache (will refill while browsing)")
        else:
            result.errors.append(proc.stderr.strip() or proc.stdout.strip() or "flushdns failed")
        return result
