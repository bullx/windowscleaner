# CONTEXT.md — agent briefing for Windows Cleaner

Read this before changing the project. It summarizes what exists, why it works that way, and what not to break.

## Purpose

Desktop + CLI tool for **Windows 10/11** that:

1. Reclaims disk space (temps, caches, logs, recycle bin)
2. Wipes local tracking residue
3. Hardens privacy via registry/policy keys
4. Disables telemetry services & scheduled tasks
5. Optionally removes preinstalled AppX bloatware and OEM/Win32 junk
6. Optionally stops unused Windows services that auto-start or sit in memory (`startup_services`)

**Not** a background resident “optimizer.” Work runs only during Scan / Dry-run / Clean.

## Stack

- **C# / .NET 10 / WPF** as of 2.0.0. The window is `src/WindowsCleaner.App`. Cleanup logic is `src/WindowsCleaner.Core` and does not reference WPF.
- Real system effects still matter more than UI polish.
- Do not add a second UI toolkit. Do not disable Defender or Windows Update.

## How to run

```powershell
cd C:\Custom\Projects\PycharmProjects\windowscleaner
dotnet build WindowsCleaner.slnx -c Release
.\src\WindowsCleaner.App\bin\Release\net10.0-windows\WindowsCleaner.exe
.\src\WindowsCleaner.App\bin\Release\net10.0-windows\WindowsCleaner.exe --cli scan
```

Portable EXE: `.\build.ps1` → `dist\WindowsCleaner.exe`. Restart a running GUI after code changes.

## Architecture

```
src/WindowsCleaner.App/Program.cs
  └─ MainWindow          # WPF, light theme
  └─ Cli.cs              # --cli
       └─ Cleaner        # profiles + scan/clean/verify
            ├─ *Module classes
            ├─ Catalogs.g.cs     # allowlists + effect text
            └─ ItemStatus, RegistryStore, Fs, PrivacyUndo, ChangeUndo
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

### Core types (`src/WindowsCleaner.Core/Models.cs`)

- `CleanModule` — `id`, `label`, `description`, `risk`, `requires_admin`, `default_enabled`
- `CleanItem` — `effect`, `repercussions`, `bytes_estimate`, `requires_admin`, **`status`**, **`next_step`**
- `ModuleResult` — per-module outcome
- `Risk` — `safe` | `moderate` | `aggressive`

### Profiles (`cleaner.py`)

| Profile | Behavior |
|---------|----------|
| `safe` | SAFE + default_enabled |
| `standard` | all default_enabled except opt-in (`bloatware`, `bloatware_oem`, `perf_services`, `startup_apps`, `startup_services`) |
| `privacy` | `privacy`, `tracking`, `telemetry_services` |
| `oem` | `bloatware` + `bloatware_oem` only |
| `disk` | space reclaim: temps, recycle, browser/GPU/system/app/dev caches, logs, AI caches |
| `workstation` | same as `disk` |
| `new_pc` | privacy + tracking + telemetry + bloat + OEM |
| `debloat` | `bloatware` + `bloatware_oem` + `startup_services` + `windows_features` |
| `ai` | `ai_caches` + `ai_history` (not model weights) |
| `full` | every module except manual ids (`perf_services`, `startup_services`, `ai_history`, `ai_models`, `system_reclaim`, `driver_store`, `dev_disks`, `windows_features`) |

### Module IDs

`temp_files`, `recycle_bin`, `browser_caches`, `browser_privacy`, `gpu_caches`, `caches`, `app_caches`, `dev_caches`, `logs`, `tracking`, `network_cache`, `privacy`, `telemetry_services`, `startup_apps`, `bloatware`, `bloatware_oem`, `startup_services`, `perf_services`, `ai_caches`, `ai_history`, `ai_models`, `dev_disks`, `system_reclaim`, `driver_store`, `windows_features`

## Important design decisions

### Safety

- Does **not** disable Defender or Windows Update
- Does **not** remove Store / Photos / Calculator / BitLocker
- Bloatware / OEM / perf services / startup apps / startup services are **opt-in** (`default_enabled=False`)
- Prefer Scan → Dry-run → Clean; optional System Restore before Clean
- Per-item Include filter: GUI passes `only_ids` into `Cleaner.clean` / each module `clean(..., only_ids=)`
- Privacy Clean records previous DWORD values → `%LOCALAPPDATA%\WindowsCleaner\privacy_undo.json` (Undo Privacy)
- User-facing disclaimer: `windowscleaner/disclaimer.py` (`DISCLAIMER_FULL` / `DISCLAIMER_SHORT`) — shown in GUI, CLI banner, Clean confirm, README
- Methods are public Windows mechanisms (folders, `winreg`, `sc`/`schtasks`, AppX PowerShell, winget, `SHEmptyRecycleBin`) — aligned with Win11Debloat / WinUtil / ShutUp10-style / Sophia task lists — **no exploits**

### Bloatware and startup services (v1.3.0)

- Human docs: README section “Debloat: default apps and startup services”. Security scope: `SECURITY.md`.
- `bloatware` allowlist: `Catalogs.Bloat` (installed + provisioned). Store, Photos, Calculator, codecs, and Defender stay off the list.
- `startup_services` allowlist: `Catalogs.StartupServices`.
  - Scan offers a service only when it exists and is not already Disabled. **Disabled** targets are offered if Automatic or currently running. **Manual** (`demand`) targets are offered only when Automatic, so features can still start an already-manual service.
  - Clean runs `sc stop` and `sc config start= disabled|demand`. Per-user services use id prefix `usvc:` and the template name plus `Name_<id>` instances.
  - Do not add Defender, Update, BITS, firewall, SmartScreen, audio, Wi-Fi, Bluetooth, Windows Hello, Store licensing, or Hyper-V / WSL (`vmcompute`, `HvHost`, `hns`, `LxssManager`). Do not duplicate `telemetry_services` or `perf_services` names.
- `MANUAL_PRESET_IDS` (`perf_services`, `startup_services`) stay off in the **full** preset. Profile `debloat` is the explicit on-switch for bloat + OEM + startup services.
- GUI copy for these rows is set on the `CleanItem` and reinforced from `Catalogs.ItemInfo`.

### Admin / status after Clean

- Many privacy keys live under `HKLM` or `HKCU\SOFTWARE\Policies\…` and return **Access Denied** without elevation
- Privacy scan/clean: Admin needed for `HKLM` **and** paths containing `\Policies\`
- Without Admin, sticky items must show **Failed — Needs Admin** / Scan **Needs Admin** — never fake success
- Temp/browser/GPU caches **refill during normal use** → later Scan **Came back** (expected)
- Locked files → **Still present** after verify; next Scan can keep that via history `reason=partial`
- `network_cache` is a flush action; scan does not pretend it is reclaimable junk every time
- Status engine: `utils/item_status.py`
  - `MODULE_KIND`: ephemeral vs sticky vs maintenance
  - `ADMIN_MODULES`: `privacy`, `telemetry_services`, `bloatware`, `bloatware_oem`, `perf_services`, `startup_services`, `system_reclaim`, `driver_store`, `windows_features` (scan labeling)
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

### GUI (`src/WindowsCleaner.App/MainWindow.xaml`)

- Light theme. Palette: background `#F8FAFC`, foreground `#0F172A`, primary `#1E3A5F`, accent `#059669`. Font: Fira Sans, then Segoe UI.
- Columns: Clean?, Status, What to do, Risk, Module, Item, Size, What it does, Repercussions, Detail
- Header click sorts. Column edges resize. The grid scrolls horizontally.
- Elevation relaunches the same EXE with `runas` (`Admin.RelaunchAsAdmin`)

### Effect / repercussions text

- Central map: `Catalogs.ItemInfo` → `ItemText.Enrich` from `Cleaner.Scan` / `Clean`
- Privacy repercussions keyed by setting id in `PRIVACY_REPERCUSSIONS`

## Dependencies

.NET 10 SDK. The WPF app and the core library have no NuGet packages. Tests use xUnit.

## Build / distribute

- `build.ps1` publishes a self-contained single-file `dist\WindowsCleaner.exe`
- The manifest stays `asInvoker`. The app asks for Administrator with `runas` when you click Restart as Administrator.
- Unsigned EXE → SmartScreen “Run anyway” for recipients

## Files agents usually touch

| Change | Where |
|--------|--------|
| New cleanup target | a `CleanModule` class + `ModuleCatalog.All()` |
| Status / verify / history | `ItemStatus.cs` + `Cleaner.cs` |
| Effect/repercussion copy | `Catalogs.ItemInfo` |
| Privacy registry keys | `Catalogs.Privacy` |
| Privacy undo | `PrivacyUndo` |
| Bloat / OEM / startup services | `Catalogs.Bloat`, `Catalogs.OemAppx`, `Catalogs.WingetTargets`, `Catalogs.StartupServices` |
| AI path allowlist | `AiPaths` in `AiModules.cs` |
| Profiles | `ModuleCatalog.Select` |
| UI | `MainWindow.xaml` |
| CLI | `Cli.cs` |
| Docs for humans | `README.md` |
| Docs for agents | `CONTEXT.md` (this file) |

## Do not

- Disable Windows Defender / wuauserv as a “tweak”
- Add Defender, Update, firewall, audio, Wi-Fi, Bluetooth, Windows Hello, or Hyper-V/WSL services to `startup_services`
- Delete in-use driver packages, or put `/ResetBase` on by default
- Put AI chats, model weights, or WSL compact on the Free disk / standard profiles
- Search the disk for “AI” folders. Clean only the named allowlist
- Force-remove Edge / break WinRE / resize partitions
- Reintroduce silent whole-module Admin skips (items must appear with Failed — Needs Admin)
- Fake Clean success without verify, or remove Fixed / Not fixed / Still present
- Commit secrets; this repo has no API keys by design

## Known UX truths to preserve

1. User must elevate for privacy/services to persist  
2. Cache modules returning after Clean is normal (**Came back**)  
3. After Clean, Status must reflect **re-scan verify** (Fixed / Not fixed / Still present)  
4. Results must show **Status**, **What to do**, **what it does**, **repercussions**  
5. Light theme GUI is intentional  

## Version / status

- App version: `AppInfo.Version` in `Models.cs` (2.0.0)
- Stack: .NET 10, WPF, CLI in the same EXE
- Project path: `C:\Custom\Projects\PycharmProjects\windowscleaner`
- Human docs: `README.md` — keep in sync when Status meanings or module IDs change
