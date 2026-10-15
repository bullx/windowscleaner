"""Superseded OEM driver packages. In-use drivers are not offered."""

from __future__ import annotations

import re
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk, allow_item
from windowscleaner.modules.system_reclaim import system32
from windowscleaner.utils.admin import is_admin
from windowscleaner.utils.proc import run_hidden

_BLOCK = re.compile(r"(?=Published Name:\s*)", re.I)


@dataclass(frozen=True)
class DriverPkg:
    published: str
    provider: str
    class_name: str
    version: str
    original: str


def _field(block: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*(.+)", block, re.I)
    return match.group(1).strip() if match else ""


def parse_enum_drivers(text: str) -> list[DriverPkg]:
    packages: list[DriverPkg] = []
    for block in _BLOCK.split(text):
        published = _field(block, "Published Name")
        if not published:
            continue
        packages.append(
            DriverPkg(
                published=published,
                provider=_field(block, "Provider Name"),
                class_name=_field(block, "Class Name"),
                version=_field(block, "Driver Version"),
                original=_field(block, "Original Name"),
            )
        )
    return packages


def in_use_published_names(text: str) -> set[str]:
    return {match.lower() for match in re.findall(r"oem\d+\.inf", text, re.I)}


def superseded_packages(packages: list[DriverPkg], in_use: set[str]) -> list[DriverPkg]:
    used = {name.lower() for name in in_use}
    chosen: list[DriverPkg] = []
    for pkg in packages:
        published = pkg.published.lower()
        if not published.startswith("oem") or not published.endswith(".inf"):
            continue
        if published in used:
            continue
        chosen.append(pkg)
    return chosen


class DriverStoreModule(CleanModule):
    id = "driver_store"
    label = "Old Drivers"
    description = (
        "Driver packages in the driver store that no connected device is using. "
        "The in-use driver is not listed. Opt-in, needs Administrator, and not in Full. "
        "Removal is one-way."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        pnputil = str(system32() / "pnputil.exe")
        if progress:
            progress("Listing driver packages")
        try:
            listed = run_hidden([pnputil, "/enum-drivers"], timeout=180)
            devices = run_hidden([pnputil, "/enum-devices", "/connected", "/drivers"], timeout=180)
        except OSError as exc:
            result.errors.append(str(exc))
            return result
        packages = superseded_packages(
            parse_enum_drivers(listed.stdout or ""),
            in_use_published_names(devices.stdout or ""),
        )
        for pkg in packages:
            provider = pkg.provider or "Unknown provider"
            result.items.append(
                CleanItem(
                    id=f"driver:{pkg.published}",
                    label=f"{provider} {pkg.published}",
                    detail=(
                        f"{pkg.original or pkg.published} — {pkg.class_name or 'driver'} — "
                        f"{pkg.version or 'date unknown'}. Not used by a connected device. "
                        "One-way: plug-in hardware may need this package again."
                    ),
                    requires_admin=True,
                    effect=f"Removes superseded driver package {pkg.published} ({provider}).",
                    repercussions=(
                        "Does not remove the driver a connected device is using. "
                        "This package cannot be restored except by reinstalling the vendor driver."
                    ),
                    risk=self.risk.value,
                )
            )
        return result

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        result = self.scan(progress)
        result.items = [item for item in result.items if allow_item(item.id, only_ids)]
        result.dry_run = dry_run
        if dry_run:
            for item in result.items:
                result.actions.append(f"Would remove {item.label}")
            return result
        admin = is_admin()
        pnputil = str(system32() / "pnputil.exe")
        for item in result.items:
            if progress:
                progress(f"Removing {item.label}")
            if not admin:
                item.detail = "Needs Administrator - not removed (will show again on Scan)"
                result.errors.append(f"{item.id}: needs Administrator")
                continue
            published = item.id.split(":", 1)[1]
            # No /force: an in-use package must fail instead of being removed.
            proc = run_hidden([pnputil, "/delete-driver", published, "/uninstall"], timeout=180)
            if proc.returncode == 0:
                result.actions.append(f"Removed {published}")
            else:
                err = (proc.stderr or proc.stdout or "pnputil failed").strip()
                item.detail = err[:500]
                result.errors.append(f"{item.id}: {err[:300]}")
        return result
