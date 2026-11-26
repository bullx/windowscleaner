# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-11-10

### Changed
- The app is now C# on .NET 10. The window is WPF. Scan, Dry-run, Clean, verify, profiles, and the allowlists match the previous tool.
- `dotnet test` covers profiles, status, driver parsing, and the AI path guard. It does not change the PC.

## [1.4.0] - 2026-10-12

### Added
- AI caches, local chats, and model weights (`ai_caches`, `ai_history`, `ai_models`). Named allowlist for Cursor, Claude, Codex, Copilot, Windsurf, and the other tools in the plan. Ollama and LM Studio weights start unchecked.
- App caches, developer caches, browser profiles beyond Default (Brave, Opera, Vivaldi), and a separate cookies/history module.
- System disk reclaim (component store, hibernation, shadow-copy cap, upgrade leftovers). `/ResetBase` starts unchecked.
- Old driver packages that no connected device is using.
- Docker build-cache prune and WSL virtual-disk compact. Rows start unchecked. The distro is kept.
- Extra language packs and a few optional features on the Debloat preset. The current display language stays.
- Checked-row size summary, undo for startup Run keys and service start types, weekly Free disk schedule.
- Profiles `ai` and `workstation`.

### Notes
- Free disk includes AI caches and developer caches. It does not include chats, model weights, or WSL compact.
- Amazon Q, Jan, Hugging Face, ComfyUI, and the other tools listed in plan section 16.6 are still not on the allowlist.

## [1.3.0] - 2026-10-07

### Added
- Optional Startup Services module (`startup_services`) — Fax, Xbox/Game Bar, Game DVR, print spooler, Remote Desktop listener, Phone Link helpers, and similar. Disabled or Manual only. Defender, Windows Update, audio, Wi-Fi, Bluetooth, and Windows Hello are excluded.
- Debloat preset (`debloat`) — preinstalled AppX + OEM/winget + startup services. Review rows before Clean.
- Extra inbox AppX matches: Camera, Scan, Reading List, Take a Test, Narrator QuickStart, Mahjong, Minesweeper, Jigsaw, Sudoku.

### Notes
- `startup_services` is opt-in and stays off in Standard, New laptop, and Full. Tick the module or use Debloat.
- SysMain and Windows Search stay in `perf_services`.

## [1.2.0] - 2026-08-07

### Added
- Per-item Include (☑/☐) on Scan results — Clean/Dry-run only touch checked rows
- Export last Scan/Clean report (JSON/TXT) from GUI and CLI `--export`
- Privacy undo: previous DWORD values recorded on Clean; restore via GUI or `undo-privacy`
- Startup Programs module (`startup_apps`) — opt-in Run keys + Startup folder
- Intent presets: Free disk (`disk`), New laptop (`new_pc`)
- Edition honesty banner (Home vs Pro telemetry expectations)
- Extra confirmation when Windows.old is in Clean scope
- Pre-Clean Admin checklist lists selected modules that need elevation
- Risk column on results; stronger post-clean Fixed summary
- `pyproject.toml`, smoke tests, LICENSE, CONTRIBUTING, SECURITY

### Changed
- Version bump to 1.2.0
- Profiles exclude `startup_apps` from standard (opt-in)

### Notes
- Code signing is not included; unsigned EXE may show SmartScreen — sign locally if you distribute widely
- GitHub Actions Release automation remains skipped (manual `.\build.ps1` + upload)

## [1.1.0] - 2026-08-02

### Added
- Privacy/AI registry catch-up (Click to Do, Paint/Notepad/Edge AI, companion telemetry keys)
- Provisioned AppX removal + expanded bloat allowlist
- OEM / winget module (`bloatware_oem`)
- Optional SysMain/WSearch module (`perf_services`)

## [1.0.0] - 2026-07

### Added
- Initial GUI/CLI cleaner with Scan → Dry-run → Clean + verify re-scan
