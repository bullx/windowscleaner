# Windows Cleaner

Python toolkit that reclaims disk space, wipes local tracking residue, hardens privacy/telemetry settings, disables noisy telemetry services & scheduled tasks, and optionally removes preinstalled Store/OEM bloatware.

Designed for **Windows 10 / 11**. Run as Administrator for full effect (privacy policies, services, update caches, bloatware).

## Quick start

```powershell
cd C:\Custom\Projects\PycharmProjects\windowscleaner
python -m pip install -r requirements.txt

# Correct module launch (do NOT use .\windowscleaner\)
python -m windowscleaner

# Or
python main.py
```

In the GUI: pick modules (or **Safe / Standard / Privacy / OEM / Full**) → **Scan** → **Dry-run** → **Clean**.  
Use **Restart as Administrator** when privacy/services/system cleanup must stick.

## What it targets

| Module | ID | What it does | Risk |
|--------|----|--------------|------|
| Temporary Files | `temp_files` | User/system TEMP, recent shortcuts, crash dumps | Safe |
| Recycle Bin | `recycle_bin` | Empties Recycle Bin | Safe |
| Browser Caches | `browser_caches` | Edge / Chrome / Firefox caches (not passwords) | Safe |
| GPU / Shader Caches | `gpu_caches` | DirectX / NVIDIA / AMD / Intel shader caches | Safe |
| System & Update Caches | `caches` | Windows Update download cache, Delivery Optimization, thumbnails, Prefetch `*.pf`, WebCache | Moderate |
| Logs & Crash Dumps | `logs` | CBS/DISM/WU logs, minidumps, `MEMORY.DMP`, WER | Safe |
| Tracking & Activity Data | `tracking` | Timeline DBs, Search/Cortana leftovers, notifications, clipboard history, Content Delivery caches | Moderate |
| DNS / Network Cache | `network_cache` | `ipconfig /flushdns` (maintenance action; refills while browsing) | Safe |
| Privacy & Telemetry Hardening | `privacy` | Registry/policy: telemetry, ads, Copilot/Recall/Click-to-Do, Paint/Notepad/Edge AI, Widgets, Delivery Optimization, Find My Device (Win11Debloat / WinUtil / ShutUp10-style) | Moderate |
| Telemetry Services & Tasks | `telemetry_services` | DiagTrack + CEIP / Flighting / PushToInstall / Maps / Device Info / WinSAT tasks | Aggressive |
| Preinstalled Bloatware | `bloatware` | Win11Debloat-style AppX list + **provisioned** deprovision (Clipchamp, Copilot, Dev Home, Feedback Hub, OEM candy, …) | Aggressive (opt-in) |
| OEM / Win32 Bloat | `bloatware_oem` | HP/Dell/Lenovo AppX families + winget uninstall for SupportAssist / Vantage / Wolf / AV trials | Aggressive (opt-in) |
| Optional Performance Services | `perf_services` | SysMain (Superfetch) + Windows Search indexer — helps some PCs, hurts others | Aggressive (opt-in) |

### Profiles

- **safe** — SAFE modules only (temps, recycle bin, logs, DNS, browser/GPU caches)
- **standard** (default) — space reclaim + tracking wipe + privacy keys + telemetry services (no app uninstalls / no SysMain)
- **privacy** — privacy + tracking + telemetry services only
- **oem** — bloatware AppX + OEM/winget module only
- **full** — everything except optional `perf_services` (tick that module manually if you want it)

## GUI features

- Module checkboxes + presets (Safe / Standard / Privacy / Full)
- Results table with **Status**, **What to do**, **What it does**, and **Repercussions**
- **Customize columns** — show/hide Status, What to do, Module, Item, Size, etc.
- Drag column edges to resize; **Shift + mouse wheel** scrolls sideways
- Click a column header to sort; **Reset column widths** restores defaults
- Column prefs saved under `%LOCALAPPDATA%\WindowsCleaner\ui_prefs.json`
- Last Clean history saved under `%LOCALAPPDATA%\WindowsCleaner\last_clean.json` (powers Came back / Still open)
- After every real **Clean**, the app **re-scans** and sets **Fixed** / **Not fixed** / **Still present** from live state
- Optional System Restore point before Clean
- **How this works** explains public Windows mechanisms (no exploits)

### Why Scan can still list items after Clean

Use the **Status** and **What to do** columns (Clean verifies with a re-scan; history explains later Scans):

| Status | Meaning | What to do |
|--------|---------|------------|
| Ready | Found, not cleaned yet | Clean |
| Needs Admin | Requires elevation | Restart as Administrator → Clean |
| **Fixed** | Clean + re-scan confirms it is gone | Nothing (sticky should stay off) |
| **Not fixed** | Clean ran but re-scan still finds it | Elevate → Clean again |
| Still present | Files still on disk after Clean | Close apps / reboot / retry |
| Came back | Was Fixed earlier; caches/temps refilled | Normal — Clean again only if you want |
| Still open | Sticky item returned on a later Scan | Elevate → Clean again |
| Failed — Needs Admin | Could not apply without elevation | Restart as Administrator → Clean |

Also normal:
1. Temp / browser / GPU caches refill while you use Windows  
2. Locked files remain until reboot / apps close  
3. DNS flush is temporary by design  

## CLI

```powershell
python -m windowscleaner --cli modules
python -m windowscleaner --cli scan
python -m windowscleaner --cli clean --dry-run
python -m windowscleaner --cli --elevate clean --profile standard -y
python -m windowscleaner --cli --elevate clean --profile full -y
python -m windowscleaner --cli --elevate clean --profile oem -y
python -m windowscleaner --cli --elevate clean --only perf_services -y
python -m windowscleaner --cli clean --only privacy,tracking -y
```

## Distribute so anyone can run (no Python)

Best option for friends / non-technical users: a **single `.exe`**.

### Build the portable EXE (on your PC)

```powershell
cd C:\Custom\Projects\PycharmProjects\windowscleaner
.\build.ps1
# or double-click build.bat
```

Output:

- `dist\WindowsCleaner.exe` — share this file  
- `dist\WindowsCleaner-portable.zip` — same EXE zipped (from `build.ps1`)

### What recipients do

1. Download / unzip  
2. Double-click **WindowsCleaner.exe**  
3. For privacy / services / update cache / bloatware: click **Restart as Administrator** and accept UAC  

No Python install required. Windows may show SmartScreen on unsigned EXEs — **More info → Run anyway** (or code-sign the EXE if you distribute widely).

| Method | Best for | Notes |
|--------|----------|--------|
| `WindowsCleaner.exe` / zip | Most people | Recommended |
| Folder + `python -m windowscleaner` | Developers | Needs Python 3.11+ and `pip install -r requirements.txt` |
| GitHub Release | Public project | Upload the zip from `dist\` as a Release asset |

## Disclaimer

**Use at your own risk.** Windows Cleaner is provided “as is”, without warranty of any kind. You are responsible for changes made to your PC. The authors are not liable for data loss, broken apps, lost OEM utilities, or any other damage.

- Not affiliated with, endorsed by, or sponsored by **Microsoft** or any PC OEM.
- Prefer **Scan → Dry-run → Clean**. Enable a **System Restore** point before Clean when available.
- **Bloatware / OEM / Windows.old** removal can be hard or impossible to undo without reinstalling apps or losing rollback.
- Privacy and service changes are usually reversible via Registry, `services.msc`, and Task Scheduler — but test carefully.
- Optional **SysMain / Windows Search** disables can help or hurt performance depending on your hardware.
- Windows **Home** may still send Required diagnostic data even when telemetry policies are applied.
- This tool does **not** disable Windows Defender or Windows Update, and avoids breaking Store / BitLocker.
- Methods use documented Windows APIs (folders, registry policies, services, Task Scheduler, AppX, winget) — aligned with Win11Debloat / WinUtil / ShutUp10-style guides. No exploits.

In the GUI: open **Disclaimer**. In the CLI: `python -m windowscleaner --cli disclaimer`.

## Safety notes

- Prefer **Scan** / **Dry-run** first.
- **Bloatware removal is irreversible** without reinstalling from the Microsoft Store — `full` / `bloatware` / `oem` are opt-in.
- OEM agents (SupportAssist, HP Wolf, Lenovo Vantage, AV trials) may reinstall via drivers/BIOS; prefer vendor removers for full AV suites.
- Prefetch cleanup may make the *next* few cold boots slightly slower.
- Deleting **Windows.old** permanently removes the previous Windows install / rollback.

## Project layout

```
windowscleaner/
  modules/          # one cleaner per concern (+ item effect/repercussion text)
                    # incl. bloatware (provisioned), bloatware_oem, perf_services
  utils/            # admin, fs, registry, sizes, restore point, item_status (verify)
  ui/gui.py         # light-theme desktop UI
  ui/cli.py         # Rich + Click CLI
  cleaner.py        # orchestrator + profiles + post-clean verify
main.py
CONTEXT.md          # agent briefing (read this in new sessions)
plan.md             # improvement plan / decisions
windowscleaner.spec # PyInstaller build
build.ps1 / build.bat
requirements.txt
```

## Requirements

- Windows 10/11  
- Python 3.11+ (developers)  
- Packages: `rich`, `click` (see `requirements.txt`)

## For AI / coding agents

See **[CONTEXT.md](CONTEXT.md)** for architecture, module map, design decisions, performance notes, Admin pitfalls, and what not to break.
