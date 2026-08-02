# CONTEXT.md — agent briefing for Windows Cleaner

Read this before changing the project. It summarizes what exists, why it works that way, and what not to break.

## Purpose

Desktop + CLI tool for **Windows 10/11** that:

1. Reclaims disk space (temps, caches, logs, recycle bin)
2. Wipes local tracking residue
3. Hardens privacy via registry/policy keys
4. Disables telemetry services & scheduled tasks
5. Optionally removes preinstalled AppX bloatware

**Not** a background resident “optimizer.” Work runs only during Scan / Dry-run / Clean.

## Stack decision (session note)

- **Stay on Python** for this project (GUI + CLI + modules).
- User cares most about **real system effects**, not UI polish.
- Do **not** rewrite to C# / C++ / C or add a C# hybrid helper unless the user explicitly asks — same Win32 outcomes, much higher cost.
- If they ever leave Python later: C# ≫ C++ ≫ C; not needed now.

## How to run

```powershell
cd C:\Custom\Projects\PycharmProjects\windowscleaner
python -m pip install -r requirements.txt

# GUI (default) — module name only, NO .\ prefix
python -m windowscleaner
python main.py

# CLI
python -m windowscleaner --cli scan
python -m windowscleaner --cli --elevate clean --profile standard -y
```

Portable EXE: `.\build.ps1` → `dist\WindowsCleaner.exe`  
Restart a running GUI after code changes — old process won’t pick them up.

## Architecture

```
main.py / windowscleaner/__main__.py
  └─ ui/gui.py          # default light-theme Tk UI
  └─ ui/cli.py          # Click + Rich (--cli)
       └─ cleaner.py    # Cleaner + select_modules(profiles)
            ├─ modules/*           # CleanModule.scan / .clean
            ├─ modules/item_info.py  # effect + repercussions text
            └─ utils/
                 ├─ item_status.py   # Status / What to do + verify + history
                 ├─ admin.py, registry.py, fs.py, size.py, restore_point.py
```

### Clean pipeline (must preserve)

1. `mod.clean()` — modules set per-item failures (`Needs Administrator` in detail / errors)
2. `annotate_clean_result()` — provisional Cleaned / Applied / Failed — Needs Admin
3. **Re-scan every cleaned module** → `verify_clean_results()` sets truth:
   - **Fixed** — gone on re-scan
   - **Not fixed** — sticky still detected
   - **Still present** — files remain (locked/partial)
   - keep **Failed — Needs Admin** when elevation blocked it
4. `record_clean_report()` → `%LOCALAPPDATA%\WindowsCleaner\last_clean.json`
5. Next **Scan** uses history → Came back / Still open / Needs Admin / Still present / Ready

`CleanReport.verify_counts` holds Fixed / Not fixed / … tallies for the GUI summary.

### Core types (`modules/base.py`)

- `CleanModule` — `id`, `label`, `description`, `risk`, `requires_admin`, `default_enabled`
- `CleanItem` — `effect`, `repercussions`, `bytes_estimate`, `requires_admin`, **`status`**, **`next_step`**
- `ModuleResult` — per-module outcome
- `Risk` — `safe` | `moderate` | `aggressive`

### Profiles (`cleaner.py`)

| Profile | Behavior |
|---------|----------|
| `safe` | SAFE + default_enabled |
| `standard` | all default_enabled except opt-in (`bloatware`, `bloatware_oem`, `perf_services`) |
| `privacy` | `privacy`, `tracking`, `telemetry_services` |
| `oem` | `bloatware` + `bloatware_oem` only |
| `full` | every module except `perf_services` (manual tick) |

### Module IDs

`temp_files`, `recycle_bin`, `browser_caches`, `gpu_caches`, `caches`, `logs`, `tracking`, `network_cache`, `privacy`, `telemetry_services`, `bloatware`, `bloatware_oem`, `perf_services`

## Important design decisions

### Safety

- Does **not** disable Defender or Windows Update
- Does **not** remove Store / Photos / Calculator / BitLocker
- Bloatware / OEM / perf services are **opt-in** (`default_enabled=False`)
- Prefer Scan → Dry-run → Clean; optional System Restore before Clean
- User-facing disclaimer: `windowscleaner/disclaimer.py` (`DISCLAIMER_FULL` / `DISCLAIMER_SHORT`) — shown in GUI, CLI banner, Clean confirm, README
- Methods are public Windows mechanisms (folders, `winreg`, `sc`/`schtasks`, AppX PowerShell, winget, `SHEmptyRecycleBin`) — aligned with Win11Debloat / WinUtil / ShutUp10-style / Sophia task lists — **no exploits**

### Admin / status after Clean

- Many privacy keys live under `HKLM` or `HKCU\SOFTWARE\Policies\…` and return **Access Denied** without elevation
- Privacy scan/clean: Admin needed for `HKLM` **and** paths containing `\Policies\`
- Without Admin, sticky items must show **Failed — Needs Admin** / Scan **Needs Admin** — never fake success
- Temp/browser/GPU caches **refill during normal use** → later Scan **Came back** (expected)
- Locked files → **Still present** after verify; next Scan can keep that via history `reason=partial`
- `network_cache` is a flush action; scan does not pretend it is reclaimable junk every time
- Status engine: `utils/item_status.py`
  - `MODULE_KIND`: ephemeral vs sticky vs maintenance
  - `ADMIN_MODULES`: `privacy`, `telemetry_services`, `bloatware`, `bloatware_oem`, `perf_services` (scan labeling)
  - History: `%LOCALAPPDATA%\WindowsCleaner\last_clean.json`
- **Cleaner does not silently skip whole modules** — each module handles Admin per item
- `caches.requires_admin = False` at module level so thumbnails/WebCache can clean without elevation; WU/DO/prefetch items still `requires_admin=True` per item
- GUI columns: **Status**, **What to do**, Module, Item, Size, effect, repercussions, detail
- GUI prompts to elevate when Admin-needed modules are selected; post-clean dialog uses **verify_counts** (no separate light-only rescan that wipes the table)

### Registry (`utils/registry.py`)

- Reads/writes use `KEY_WOW64_64KEY` so 32-bit Python matches 64-bit view
- `CreateKeyEx` uses `KEY_READ | KEY_WRITE` (not `KEY_SET_VALUE` alone — that failed with WinError 2)
- Writes are verified with read-back (`values_match`)

### Performance

- Folder sizing uses `os.scandir` + symlink skip + soft file-count cap (`utils/size.py`)
- Real Clean should **not** double-walk for delete sizing: dry-run may scan sizes; live clean deletes in one pass
- Post-clean **verify re-scan is intentional** (correctness over skipping TEMP walks)
- Avoid `Path.rglob` on huge package trees; prefer shallow globs
- Subprocesses use `CREATE_NO_WINDOW` where available
- Bloatware: current-user `Get-AppxPackage` first; `-AllUsers` only when elevated
- PyInstaller: do **not** `collect_all("rich")` (pulls IPython/numpy); keep excludes lean (`windowscleaner.spec`)

### GUI (`ui/gui.py`)

- Light theme (user requested; avoid dark default)
- Default visible: Status, What to do, Module, Item, Size, What it does, Repercussions
- **All columns `stretch=False`** so horizontal scrollbar works
- Customize columns / resize / Shift+wheel horizontal scroll / header sort
- Prefs: `%LOCALAPPDATA%\WindowsCleaner\ui_prefs.json` (auto-injects `status` / `next_step` if old prefs lack them)
- Frozen EXE elevation: `sys.frozen` → relaunch same EXE with `runas` (`utils/admin.py`)

### Effect / repercussions text

- Central map: `modules/item_info.py` → `enrich_result()` called from `Cleaner.scan/clean`
- Privacy repercussions keyed by setting id in `PRIVACY_REPERCUSSIONS`

## Dependencies

`requirements.txt`: `rich`, `click`  
(Tkinter is stdlib on Windows CPython. `psutil` was removed — unused.)

## Build / distribute

- `build.ps1` / `build.bat` → PyInstaller one-file `WindowsCleaner.exe`
- Spec: `windowscleaner.spec`, `console=False`, `uac_admin=False` (in-app elevate)
- Unsigned EXE → SmartScreen “Run anyway” for recipients
- Rebuild EXE after status/verify changes if distributing

## Files agents usually touch

| Change | Where |
|--------|--------|
| New cleanup target | new or existing `modules/*.py` + register in `modules/__init__.py` `all_modules()` |
| Status / verify / history | `utils/item_status.py` + `cleaner.py` |
| Effect/repercussion copy | `modules/item_info.py` |
| Privacy registry keys | `modules/privacy.py` `SETTINGS` |
| Bloat package list + provisioned | `modules/bloatware.py` `BLOAT` |
| OEM AppX / winget | `modules/bloatware_oem.py` |
| Optional SysMain/WSearch | `modules/perf_services.py` |
| Services/tasks | `modules/telemetry_services.py` |
| Profiles | `cleaner.py` `select_modules` |
| UI behavior | `ui/gui.py` |
| CLI | `ui/cli.py` |
| Docs for humans | `README.md` |
| Docs for agents | `CONTEXT.md` (this file) |

## Do not

- Disable Windows Defender / wuauserv as a “tweak”
- Force-remove Edge / break WinRE / resize partitions
- Reintroduce silent whole-module Admin skips (items must appear with Failed — Needs Admin)
- Fake Clean success without verify, or remove Fixed / Not fixed / Still present
- Set Treeview column `stretch=True` on all columns (breaks horizontal scroll)
- Use `python -m .\windowscleaner\` — relative module paths are invalid; use `python -m windowscleaner`
- Rewrite to C#/C++/hybrid “for better system commands” unless user explicitly requests
- Commit secrets; this repo has no API keys by design

## Known UX truths to preserve

1. User must elevate for privacy/services to persist  
2. Cache modules returning after Clean is normal (**Came back**)  
3. After Clean, Status must reflect **re-scan verify** (Fixed / Not fixed / Still present)  
4. Results must show **Status**, **What to do**, **what it does**, **repercussions**  
5. Light theme GUI is intentional  

## Version / status

- App version: see `windowscleaner/__init__.py` (`__version__`)
- Stack: Python 3.11+, Tk GUI, optional Rich CLI, PyInstaller portable build
- Project path: `C:\Custom\Projects\PycharmProjects\windowscleaner`
- Human docs: `README.md` (status table + Fixed/verify) — keep in sync when Status meanings change
