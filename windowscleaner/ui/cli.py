"""Rich-powered CLI for Windows Cleaner."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from windowscleaner import __app_name__, __version__
from windowscleaner.cleaner import CleanReport, Cleaner, select_modules
from windowscleaner.disclaimer import DISCLAIMER_FULL, DISCLAIMER_SHORT
from windowscleaner.modules import all_modules
from windowscleaner.utils.admin import is_admin, relaunch_as_admin
from windowscleaner.utils.privacy_undo import load_undo, undo_all
from windowscleaner.utils.report_export import save_report
from windowscleaner.utils.size import format_bytes
from windowscleaner.utils.windows_info import edition_banner_text

console = Console(legacy_windows=False, soft_wrap=True)

PROFILE_CHOICES = ["safe", "standard", "privacy", "oem", "disk", "new_pc", "full"]


def _risk_style(risk: str) -> str:
    return {
        "safe": "green",
        "moderate": "yellow",
        "aggressive": "red",
    }.get(risk, "white")


def _print_banner() -> None:
    admin = is_admin()
    status = Text()
    status.append(__app_name__, style="bold cyan")
    status.append(f" v{__version__}\n", style="cyan")
    status.append("Disk cleanup | tracking wipe | privacy hardening | bloat removal\n")
    status.append(
        "Administrator: YES" if admin else "Administrator: NO (elevate for full cleanup)",
        style="bold green" if admin else "bold yellow",
    )
    status.append("\n")
    status.append(edition_banner_text() + "\n", style="dim")
    status.append(DISCLAIMER_SHORT, style="dim")
    console.print(Panel(status, box=box.ROUNDED, border_style="cyan"))


def _print_modules() -> None:
    table = Table(title="Available modules", box=box.SIMPLE_HEAVY)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Risk")
    table.add_column("Admin")
    table.add_column("Default")
    table.add_column("Description")

    for mod in all_modules():
        table.add_row(
            mod.id,
            mod.label,
            Text(mod.risk.value, style=_risk_style(mod.risk.value)),
            "yes" if mod.requires_admin else "no",
            "on" if mod.default_enabled else "opt-in",
            mod.description,
        )
    console.print(table)


def _render_report(report: CleanReport, *, mode: str) -> None:
    table = Table(
        title=f"{'Dry-run' if report.dry_run else mode.capitalize()} results",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Module", style="cyan")
    table.add_column("Items", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Freed", justify="right")
    table.add_column("Actions", justify="right")
    table.add_column("Errors", justify="right")

    for r in report.results:
        if not r.items and not r.actions and not r.errors:
            continue
        table.add_row(
            r.label,
            str(len(r.items)),
            format_bytes(r.bytes_estimate),
            format_bytes(r.bytes_freed),
            str(len(r.actions)),
            str(len(r.errors)),
        )

    console.print(table)

    if report.skipped_modules:
        console.print("\n[yellow]Skipped (need Administrator):[/yellow]")
        for s in report.skipped_modules:
            console.print(f"  * {_safe_text(s)}")

    # Show actionable detail for items / privacy changes
    detail = Table(title="Details", box=box.MINIMAL, show_header=True)
    detail.add_column("Status")
    detail.add_column("What to do")
    detail.add_column("Module", style="dim")
    detail.add_column("Item")
    detail.add_column("Size", justify="right")
    shown = 0
    for r in report.results:
        for item in r.items[:40]:
            size = format_bytes(item.bytes_estimate) if item.bytes_estimate else "-"
            detail.add_row(
                _safe_text(item.status or "-", 18),
                _safe_text(item.next_step or "-", 36),
                _safe_text(r.label, 18),
                _safe_text(item.label, 24),
                size,
            )
            shown += 1
            if shown >= 50:
                break
        if shown >= 50:
            break
    if shown:
        console.print(detail)

    errors = [(r.label, e) for r in report.results for e in r.errors[:5]]
    if errors:
        console.print("\n[red]Errors (sample):[/red]")
        for label, err in errors[:20]:
            console.print(f"  * [{_safe_text(label, 24)}] {_safe_text(err, 100)}")

    summary = Text()
    summary.append("Items: ", style="bold")
    summary.append(f"{report.item_count}   ")
    summary.append("Estimated reclaimable: ", style="bold")
    summary.append(f"{format_bytes(report.bytes_estimate)}   ", style="green")
    if mode != "scan":
        summary.append("Freed: ", style="bold")
        summary.append(f"{format_bytes(report.bytes_freed)}   ", style="green")
        summary.append("Actions: ", style="bold")
        summary.append(f"{report.action_count}   ")
    summary.append("Errors: ", style="bold")
    summary.append(str(report.error_count), style="red" if report.error_count else "green")
    console.print(Panel(summary, title="Summary", border_style="green"))


def _safe_text(value: str, limit: int = 90) -> str:
    text = "".join(ch if ord(ch) < 128 else "?" for ch in str(value))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _parse_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def _run_with_progress(fn):
    messages: list[str] = []

    def progress(msg: str) -> None:
        messages.append(msg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as bar:
        task = bar.add_task("Working...", total=None)

        def progress_ui(msg: str) -> None:
            progress(msg)
            bar.update(task, description=msg[:80])

        return fn(progress_ui)


@click.group(invoke_without_command=True)
@click.option("--elevate", is_flag=True, help="Relaunch with Administrator rights via UAC.")
@click.version_option(__version__, prog_name=__app_name__)
@click.pass_context
def main(ctx: click.Context, elevate: bool) -> None:
    """Windows Cleaner - reclaim space, wipe tracking data, harden privacy."""
    if elevate and not is_admin():
        console.print("[yellow]Requesting Administrator elevation...[/yellow]")
        relaunch_as_admin()
        sys.exit(0)

    if ctx.invoked_subcommand is None:
        _print_banner()
        console.print(
            "Commands: [cyan]scan[/cyan] | [cyan]clean[/cyan] | "
            "[cyan]modules[/cyan] | [cyan]doctor[/cyan] | [cyan]disclaimer[/cyan]\n"
            "Try: [bold]python -m windowscleaner scan[/bold]    "
            "or  [bold]python -m windowscleaner clean --dry-run[/bold]\n"
            "Full cleanup (admin): [bold]python -m windowscleaner --elevate clean --profile full[/bold]"
        )


@main.command("disclaimer")
def disclaimer_cmd() -> None:
    """Show the full disclaimer."""
    console.print(Panel(DISCLAIMER_FULL.strip(), title="Disclaimer", border_style="yellow"))


@main.command("modules")
def modules_cmd() -> None:
    """List cleanup modules and risk levels."""
    _print_banner()
    _print_modules()


@main.command("doctor")
def doctor_cmd() -> None:
    """Show environment / elevation status."""
    _print_banner()
    table = Table(box=box.SIMPLE)
    table.add_column("Check")
    table.add_column("Value")
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Administrator", "yes" if is_admin() else "no")
    table.add_row("Platform", sys.platform)
    console.print(table)
    if not is_admin():
        console.print(
            "\n[yellow]Tip:[/yellow] re-run with "
            "[bold]python -m windowscleaner --elevate <command>[/bold] "
            "for Windows Update cache, logs, privacy policies, and services."
        )


@main.command("scan")
@click.option(
    "--profile",
    type=click.Choice(PROFILE_CHOICES, case_sensitive=False),
    default="standard",
    show_default=True,
    help="Which module set to include.",
)
@click.option("--only", default=None, help="Comma-separated module IDs.")
@click.option("--exclude", default=None, help="Comma-separated module IDs to skip.")
@click.option("--export", "export_path", default=None, help="Write JSON/TXT report to this path.")
def scan_cmd(profile: str, only: Optional[str], exclude: Optional[str], export_path: Optional[str]) -> None:
    """Scan for reclaimable junk and privacy drift (no changes)."""
    _print_banner()
    mods = select_modules(only=_parse_csv(only), exclude=_parse_csv(exclude), profile=profile.lower())
    if not mods:
        console.print("[red]No modules selected.[/red]")
        sys.exit(1)
    console.print(f"Profile: [bold]{profile}[/bold]  Modules: {', '.join(m.id for m in mods)}\n")

    cleaner = Cleaner(mods)
    report = _run_with_progress(lambda cb: cleaner.scan(cb))
    _render_report(report, mode="scan")
    if export_path:
        path = save_report(report, mode="scan", path=Path(export_path))
        console.print(f"\n[green]Exported[/green] {path}")


@main.command("clean")
@click.option(
    "--profile",
    type=click.Choice(PROFILE_CHOICES, case_sensitive=False),
    default="standard",
    show_default=True,
    help="Which module set to include.",
)
@click.option("--only", default=None, help="Comma-separated module IDs.")
@click.option("--exclude", default=None, help="Comma-separated module IDs to skip.")
@click.option("--dry-run", is_flag=True, help="Show what would happen without changing anything.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--export", "export_path", default=None, help="Write JSON/TXT report to this path.")
def clean_cmd(
    profile: str,
    only: Optional[str],
    exclude: Optional[str],
    dry_run: bool,
    yes: bool,
    export_path: Optional[str],
) -> None:
    """Clean junk / apply privacy hardening."""
    _print_banner()
    mods = select_modules(only=_parse_csv(only), exclude=_parse_csv(exclude), profile=profile.lower())
    if not mods:
        console.print("[red]No modules selected.[/red]")
        sys.exit(1)

    console.print(f"Profile: [bold]{profile}[/bold]  Modules: {', '.join(m.id for m in mods)}")
    admin_needed = [m.label for m in mods if m.requires_admin]
    if admin_needed and not is_admin():
        console.print("[yellow]Modules that typically need Administrator:[/yellow]")
        for n in admin_needed:
            console.print(f"  • {n}")
    if dry_run:
        console.print("[yellow]Dry-run mode - no changes will be made.[/yellow]\n")
    else:
        console.print(
            "[red]This will delete files and/or change system settings.[/red]\n"
            f"[dim]{DISCLAIMER_SHORT}[/dim]\n"
        )

    if not dry_run and not yes:
        if not click.confirm(
            "Continue and accept responsibility for these changes?",
            default=False,
        ):
            console.print("Aborted.")
            sys.exit(0)

    # Pre-scan so the user sees impact, then clean
    cleaner = Cleaner(mods)
    if not dry_run:
        scan_report = _run_with_progress(lambda cb: cleaner.scan(cb))
        console.print(
            f"Found [bold]{scan_report.item_count}[/bold] items · "
            f"~[bold green]{format_bytes(scan_report.bytes_estimate)}[/bold green] reclaimable\n"
        )

    report = _run_with_progress(lambda cb: cleaner.clean(dry_run=dry_run, progress=cb))
    _render_report(report, mode="clean")
    if export_path:
        path = save_report(
            report,
            mode="clean",
            path=Path(export_path),
        )
        console.print(f"\n[green]Exported[/green] {path}")

    if not is_admin() and any(m.requires_admin for m in mods):
        console.print(
            "\n[yellow]Some modules need Administrator.[/yellow] "
            "Re-run: [bold]python -m windowscleaner --elevate clean "
            f"--profile {profile} -y[/bold]"
        )


@main.command("undo-privacy")
@click.option("--dry-run", is_flag=True, help="Show what would be restored.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation.")
def undo_privacy_cmd(dry_run: bool, yes: bool) -> None:
    """Restore previous privacy registry values recorded during Clean."""
    _print_banner()
    data = load_undo()
    entries = data.get("entries") or []
    if not entries:
        console.print("[yellow]No privacy undo history found.[/yellow]")
        sys.exit(0)
    console.print(f"Recorded changes: [bold]{len(entries)}[/bold]")
    for e in entries[:20]:
        console.print(f"  • {e.get('label') or e.get('id')} (was {e.get('previous')!r})")
    if not dry_run and not yes:
        if not click.confirm("Restore these values?", default=False):
            console.print("Aborted.")
            sys.exit(0)
    ok, failed, messages = undo_all(dry_run=dry_run)
    for m in messages:
        console.print(m)
    console.print(f"\nOk: {ok}  Failed/skipped: {failed}")


if __name__ == "__main__":
    main()
