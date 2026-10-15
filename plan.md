# Windows Cleaner — Improvement Plan

**Historical plan (written 2026-08-02).**  
Shipped work since then is in [CHANGELOG.md](CHANGELOG.md). Current behavior is in [README.md](README.md) and [CONTEXT.md](CONTEXT.md).

As of **v1.3.0** (2026-10-07) the product includes provisioned AppX removal, OEM/winget (`bloatware_oem`), SysMain/WSearch (`perf_services`), startup programs, and **Optional Startup Services** (`startup_services`) plus a **debloat** profile. Sections 4–14 that say “not implemented” or “highest ROI next” describe the August 2026 backlog, not today’s app.

Unbuilt proposals: none from sections 16–17 as of **v1.4.0**. Section 16.6 still lists AI apps that are not on the allowlist yet.

Project: `C:\Custom\Projects\PycharmProjects\windowscleaner`  
Sources: current codebase, CONTEXT.md / README, Win11Debloat (2026), WinUtil / ShutUp10-style guides, OEM debloat practices

---

## 1. Goal of this document

List **everything worth considering** so you can approve, cut, or reorder work.  
The August 2026 items below were a proposal. Shipped items are marked in Section 14 and in CHANGELOG.md.

---

## 2. Current state (honest)

### What the app already does well

| Area | Coverage |
|------|----------|
| Disk reclaim | Temps, recycle bin, browser/GPU caches, WU/DO/prefetch/WebCache, logs, tracking residue, DNS flush |
| Privacy registry | ~50 curated keys: telemetry, ads/CDM, activity history, Cortana/Bing search, Copilot, Recall, Widgets, Find My Device, Edge hub/startup boost, Game DVR, Delivery Optimization |
| Services / tasks | DiagTrack, dmwappush, WER, PCA, RetailDemo, RemoteRegistry, MapsBroker, WSAIFabricSvc + CEIP / Flighting / PushToInstall / Maps / Device Info tasks |
| Bloatware | Opt-in AppX allowlist (MS consumer + Copilot/Dev Home/Widgets + common Store/OEM candy); scan then optional remove |
| UX truthfulness | Scan → Dry-run → Clean → **re-scan verify** (Fixed / Not fixed / Still present); Admin failures not faked |
| Safety rails | No Defender / Update disable; Store / Photos / Calculator / BitLocker left alone; bloatware `default_enabled=False` |

### What it is *not*

- Not a complete list of “every registry key that makes Windows slow”
- Not a full OEM suite remover (Dell SupportAssist / HP Wolf / Lenovo Vantage Win32)
- Not a visual/UI customizer (taskbar layout, Explorer chrome) like Win11Debloat’s full feature set
- Not git-initialized / not fully “public prod packaged” yet

### Important truth about “slow”

Telemetry + ads + Store bloat help **some**. Often larger drains:

1. OEM Win32 agents (SupportAssist, Wolf, Vantage, McAfee trials)
2. Startup programs / too many background apps
3. Disk nearly full, bad drivers, heavy AV scans
4. Controversial services (SysMain, Search indexer) — help some PCs, hurt others

Do **not** promise “all slow registry keys” in marketing copy.

---

## 3. Proposed workstreams

Priorities assume: keep Python stack, preserve Clean verify pipeline, stay aligned with public Windows mechanisms (no exploits), never disable Defender / wuauserv.

```
P0 = high value, fits current design, low breakage risk
P1 = strong value, needs careful UX / Admin / copy
P2 = nice-to-have or controversial — only if you explicitly want it
P3 = product/git polish (orthogonal to cleanup power)
```

---

## 4. Privacy & AI registry (`modules/privacy.py`)

### 4.1 P0 — Add missing Win11Debloat-style AI / telemetry companion keys

| Setting (proposed id) | Intent | Notes |
|----------------------|--------|--------|
| `click_to_do` / machine twin | Disable Click to Do / AI text & image analysis | Win11 24H2+; policy under WindowsAI-style paths |
| `paint_ai` | Disable Paint generative AI | Policy keys used by Win11Debloat |
| `notepad_ai` | Disable Notepad AI | Same |
| `edge_ai` | Disable Edge AI features (beyond hub/boost) | Keep Store/Update intact |
| `one_settings_downloads` | `DisableOneSettingsDownloads = 1` | Blocks remote telemetry config pulls |
| `max_telemetry_allowed` | `MaxTelemetryAllowed = 0` (or 1 on Home-safe) | Companion to `AllowTelemetry` |
| `ceip_enabled` | CEIP off via policy/SQM path | Complements task disables |
| `feedback_notifications_policy` | `DoNotShowFeedbackNotifications` | Policy-level (stickier than SIUF alone) |
| `game_dvr_enabled` | `GameDVR_Enabled = 0` | Companion to existing `AppCaptureEnabled` |
| `advertising_id_policy` | `DisabledByGroupPolicy` for AdvertisingInfo | Harder lock than HKCU Enabled=0 |
| `store_search_suggestions` | Disable Store app suggestions in Search | W11; Win11Debloat default |
| `settings_home_ads` / `ms365_ads` | Hide Settings Home / Microsoft 365 ads | Win11Debloat default |

**Also update:** `modules/item_info.py` repercussions text for each new id.

### 4.2 P1 — Edition-aware telemetry messaging

- On **Home**, `AllowTelemetry = 0` may be coerced to Required (1) by Windows — document in Status/detail, don’t claim “fully off”
- Optionally detect edition and show clearer Scan detail (“capped to Required on this edition”)

### 4.3 P2 — UI / Explorer cosmetics (only if you want a “Debloat UI” module)

Win11Debloat has many **non-performance** toggles. Candidates for a **separate** module (`ui_declutter`) so privacy stays focused:

- Show file extensions  
- Hide Chat / Meet Now (Win10)  
- Disable Drag Tray  
- Modern Standby network connectivity off (battery)  
- Hide 3D Objects (Win10)  
- Start recommendations / Phone Link in Start  
- Snap Assist / sticky keys / mouse acceleration (very opinionated — default off)

**Recommendation:** skip unless you explicitly want UI customization; it dilutes the cleaner’s job.

---

## 5. Telemetry services & tasks (`modules/telemetry_services.py`)

### 5.1 P1 — Expand task list (Sophia / community staples still missing)

Candidates to scan/disable when present:

- `\Microsoft\Windows\Application Experience\AitAgent` (if present)
- `\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticResolver` (careful — some keep for disk health)
- `\Microsoft\Windows\Power Efficiency Diagnostics\AnalyzeSystem`
- `\Microsoft\Windows\Shell\IndexerAutomaticMaintenance` (**controversial** — Search)
- WinSAT / SystemSoundsService-related CEIP tasks if still present on build
- Any new Flighting / Diagnosis paths that appear on 24H2+

### 5.2 P2 — Optional performance services (new module or aggressive profile flag)

| Service | Claim | Risk |
|---------|--------|------|
| `SysMain` (Superfetch) | Less disk thrash on HDDs / low RAM | Can slow app launch on SSDs with free RAM |
| `WSearch` | Less background indexing | Breaks Start/file search quality |
| `DiagTrack` | Already covered | Keep |

**Recommendation:** if added, put under a new module `perf_services` with `default_enabled=False` and loud repercussions — **not** in `standard` / `privacy` profiles.

---

## 6. Bloatware (`modules/bloatware.py`)

### 6.1 P0 — Align allowlist with Win11Debloat 2026 defaults (safe-ish gaps)

Add matches you don’t have yet (still opt-in; user reviews Scan):

**Microsoft (from Win11Debloat default table, missing or weak):**

- `Microsoft.WindowsAlarms` (Alarms & Clock) — mark “optional; many users keep”
- `Microsoft.Office.OneNote` (UWP OneNote)
- `Microsoft.MicrosoftPowerBIForWindows`
- Extra Copilot / Teams naming variants if Scan misses on some builds

**Third-party candy (common OEM stubs):**

- Asphalt 8, Cooking Fever, FarmVille, Hidden City, March of Empires, Royal Revolt  
- Hulu, Sling TV, iHeartRadio, TuneIn, Duolingo, Flipboard, PicsArt, WinZip UWP, etc.

Keep **out** of default remove spirit (or label clearly): Store, Photos, Calculator, Paint (unless AI-only policy), Terminal, HEVC extensions.

### 6.2 P0 — Provisioned packages (stop bloat coming back)

Today: `Get-AppxPackage` + `Remove-AppxPackage` only.  
Gap: apps remain in the **provisioned** image → return for new users / some resets.

Plan:

1. Scan via `Get-AppxProvisionedPackage -Online`  
2. On Clean (Admin): `Remove-AppxProvisionedPackage -Online` for matched packages  
3. Show Status items distinctly: `Installed` vs `Provisioned (will reappear for new users)`  
4. Preserve verify re-scan semantics

### 6.3 P1 — OEM AppX patterns (HP / Dell / Lenovo Store packages)

Add substring families Win11Debloat / community scripts use, e.g.:

- HP: `AD2F1837.*` / common HP AppX names  
- Dell: `Dell*`, `PortraitDisplays*`, etc. where AppX  
- Lenovo: `E046*` / Lenovo AppX stubs  

Still **not** full Win32 OEM nuke.

### 6.4 P1 — winget / Win32 optional path (new submodule or mode)

For non-AppX junk users actually feel:

| Target class | Method | Risk |
|--------------|--------|------|
| Spotify / Disney+ desktop stubs | `winget uninstall` when available | Medium |
| Dell SupportAssist, HP Support Assistant, Lenovo Vantage | winget + ARP / msiexec discovery | Aggressive |
| McAfee / Norton trials | Vendor removal tools preferred; don’t half-break AV | Aggressive + warn |

**Recommendation:** phase as `bloatware_oem` module, `default_enabled=False`, never in `standard`. Scan-only first release, Clean later after you validate on real OEM machines.

### 6.5 P2 — Per-item user picker in GUI

Today: whole module on/off.  
Improvement: checkbox tree or multi-select so “remove Candy Crush, keep Phone Link / Xbox” is one Clean.

---

## 7. Disk / tracking modules (smaller gains)

### 7.1 P1

| Idea | Where | Why |
|------|--------|-----|
| Delivery Optimization cache more aggressive when Admin | `caches` | Space reclaim |
| Edge / Chrome **code cache** / GPUCache paths refresh | `browser_caches` | Builds change paths |
| Windows.old detection (report size; optional remove with strong warning) | new or `caches` | Huge reclaim after feature update |
| Thumbnail DB + icon cache rebuild note | `caches` | Already partial — clarify repercussions |
| Notification DB / Timeline paths for newer builds | `tracking` | Path drift on 24H2 |

### 7.2 P2

- OneDrive leftover cleanup (aggressive; easy to anger users)  
- Windows Update component store compact (`Dism /StartComponentCleanup`) — powerful, slow, Admin-only, needs clear dry-run messaging  

---

## 8. Architecture / UX improvements

### 8.1 P0 — Keep invariants (do not break)

1. Clean → annotate → **verify re-scan** → history  
2. No silent whole-module Admin skip  
3. Fixed / Not fixed / Still present / Came back / Still open  
4. Light theme; Status + What to do columns  
5. Stay on Python unless you explicitly request a rewrite  

### 8.2 P1 — Product UX

| Item | Detail |
|------|--------|
| Risk badges in GUI | Per-item “Safe / Moderate / Aggressive” |
| Elevate prompt clarity | List which selected modules need Admin before Clean |
| Post-clean summary | Already uses verify_counts — surface “X Fixed, Y Needs Admin” more prominently |
| Edition banner | Home vs Pro telemetry expectations |
| Export report | Save last Scan/Clean as JSON/TXT for support |

### 8.3 P2 — Profiles tweak

| Profile | Possible change |
|---------|-----------------|
| `standard` | Keep: no bloatware; maybe exclude controversial perf services forever |
| `privacy` | Add new AI keys automatically (same module) |
| `full` | Include provisioned AppX removal + (later) OEM module |
| New `oem` | Only OEM / winget targets |

---

## 9. Git / production readiness (orthogonal)

Current: `.gitignore` exists; **no git init**; no LICENSE; no tests; `dist/`/`build/` local only (ignored).

### 9.1 P3 — Minimal git-ready

- `git init`  
- LICENSE (suggest MIT unless you prefer another)  
- CHANGELOG.md (Keep a Changelog style)  
- Confirm `.gitignore` covers `__pycache__`, `.venv`, `dist/`, `build/`, `.idea/`  
- First commit of source only (never commit `WindowsCleaner.exe` unless you want Release assets elsewhere)  
- Keep or drop `CONTEXT.md` in public repo (agent-useful; unusual for end users — recommend **keep**)

### 9.2 P3 — Solid package

- `pyproject.toml` (name, version synced with `windowscleaner/__init__.py`, requires-python `>=3.11`, deps)  
- Pin or lock deps (`requirements.txt` + optional `requirements-dev.txt`)  
- Smoke tests: import modules, `select_modules` profiles, registry values_match unit tests (no live system mutation in CI)  
- CONTRIBUTING.md + SECURITY.md (disclosure contact)  

### 9.3 P3 — Ship pipeline

**Decision (2026-08-02): releases are manual — skip automated GitHub Actions Release builds (Phase E++).**

Release workflow you will use:

1. On your PC: `.\build.ps1` → `dist\WindowsCleaner-portable.zip`  
2. Create a GitHub Release (or share the zip however you like)  
3. Upload the zip / EXE yourself as the Release asset  

Still optional later (not planned unless you ask):

- GitHub Actions for **tests only** on push (no EXE build)  
- Code signing certificate (reduces SmartScreen friction)  
- Automated tag → build → upload (Phase E++ — **declined**)  

SmartScreen note stays in README for unsigned EXEs.

---

## 10. Explicit non-goals (do not do)

Unless you override in writing:

- [ ] Disable Windows Defender / Tamper Protection  
- [ ] Disable `wuauserv` / break Windows Update  
- [ ] Force-remove Microsoft Edge / break WebView2 for other apps  
- [ ] Touch BitLocker, disk partitions, WinRE  
- [ ] Fake Clean success without verify  
- [ ] Silent skip of Admin-needed items  
- [ ] Rewrite to C# / C++ “for better system commands”  
- [ ] Bundle exploits / undocument hacks  
- [ ] Auto-enable SysMain/WSearch disable in `standard`  

---

## 11. Suggested implementation phases

### Phase A — Privacy/AI catch-up (smallest blast radius)

1. Add P0 registry keys + `item_info` copy  
2. Manual Admin Scan/Clean on Win10 + Win11 24H2  
3. Update README / CONTEXT status tables if Status meanings unchanged (copy only for new settings)

### Phase B — Bloatware durability

1. Expand AppX allowlist from Win11Debloat gaps  
2. Provisioned package scan + remove  
3. Distinct Status/detail for provisioned vs installed  
4. Verify Fixed means gone from both lists when possible  

### Phase C — OEM / winget (opt-in aggressive)

1. Scan-only OEM AppX + winget inventorial  
2. Clean behind extra confirmation dialog  
3. Test on at least one HP/Dell/Lenovo machine before advertising  

### Phase D — Optional perf module

1. SysMain / WSearch as separate opt-in module  
2. Never default-on  

### Phase E — Git / prod

1. License + changelog + init  
2. `pyproject.toml` + smoke tests  
3. ~~GitHub Actions Release zip~~ — **skipped**; you upload Release assets manually after `.\build.ps1`

---

## 12. File touch map (when implementing)

| Change | Files |
|--------|--------|
| New privacy keys | `windowscleaner/modules/privacy.py`, `modules/item_info.py` |
| Services/tasks | `windowscleaner/modules/telemetry_services.py`, `item_info.py` |
| AppX list / provisioned | `windowscleaner/modules/bloatware.py` |
| New OEM / perf modules | new `modules/*.py` + register in `modules/__init__.py` + profiles in `cleaner.py` |
| Status kinds if new sticky types | `utils/item_status.py` |
| GUI picker / banners | `ui/gui.py` |
| CLI flags | `ui/cli.py` |
| Docs | `README.md`, `CONTEXT.md` |
| Packaging | `pyproject.toml`, `LICENSE`, `CHANGELOG.md` (no Release workflow — manual upload) |

---

## 13. Acceptance criteria (per phase)

### Phase A done when

- [ ] New keys appear on Scan when drifted  
- [ ] Clean + verify shows Fixed or Failed — Needs Admin correctly  
- [ ] No Defender/Update touched  
- [ ] Dry-run changes nothing  

### Phase B done when

- [ ] Scan shows provisioned matches even if not installed for current user  
- [ ] Clean removes provisioned entry (Admin)  
- [ ] New local user does not get those apps back (spot-check)  

### Phase C done when

- [ ] OEM targets listed with clear repercussions  
- [ ] Default profiles never auto-enable OEM Clean  
- [ ] Failure modes (winget missing, MSI busy) surface as Failed / Still present  

### Phase E done when

- [ ] Fresh clone → `pip install` → `python -m windowscleaner` works  
- [ ] `build.ps1` still produces portable zip  
- [ ] Secrets/binaries not in git history  

---

## 14. Decision checklist (fill in when reviewing)

Copy and mark:

```
[x] Phase A — Privacy/AI registry keys          → DONE (v1.1.0)
[x] Phase B — AppX list + provisioned removal   → DONE
[x] Phase C — OEM / winget module               → DONE (`bloatware_oem`)
[x] Phase D — SysMain/WSearch opt-in perf module → DONE (`perf_services`)
[x] Phase E — Git basics (LICENSE, changelog)   → DONE (v1.2.0; repo already had git)
[x] Phase E+ — pyproject + tests                → DONE (v1.2.0)
[x] Phase E++ — GitHub Actions + Release zip  → SKIPPED (manual upload)

[x] Phase F — Product maturity (P0–P3)          → DONE (v1.2.0)
    - Per-item Include + only_ids clean path
    - Admin pre-check module list, export report, stronger verify summary
    - Startup apps module, edition banner, Windows.old confirm
    - Privacy undo + applied-changes export
    - Intent presets disk/new_pc; utils split (windows_info, report_export, privacy_undo)

[x] Phase G — Debloat + startup services       → DONE (v1.3.0)
    - startup_services opt-in (Disabled or Manual; never Defender/Update/Hello/audio/Wi-Fi)
    - debloat profile = bloatware + bloatware_oem + startup_services
    - extra inbox AppX matches (Camera, Scan, games, Narrator QuickStart, Take a Test)
    - full preset still excludes perf_services and startup_services

Release process: .\build.ps1 locally → upload zip/EXE to GitHub Release yourself
UI declutter module: no (skipped — dilutes cleaner focus)
Code signing: document only (no cert in repo)
```

---

## 15. Bottom line

| Question | Answer (as of v1.3.0) |
|----------|------------------------|
| All slow-making registry keys today? | **No** — privacy/telemetry/AI policy set is in `privacy`. This is not a full ShutUp10 clone. |
| Optional bloatware scan/remove today? | **Yes** — `bloatware` (installed + provisioned) and `bloatware_oem`. Opt-in. Debloat preset turns both on. |
| Unused startup services? | **Yes** — `startup_services`, opt-in, included by **debloat**, excluded from **full**. Undo in `services.msc`. |
| SysMain / Windows Search? | **Yes** — `perf_services` only. Not part of Debloat or Full. |
| Git/prod? | pyproject, tests, LICENSE, changelog. Release zip is still a manual `.\build.ps1` upload. |
| Cursor / Claude / other AI tool folders? | **Yes, allowlist only** — `ai_caches`, `ai_history`, `ai_models` (v1.4.0). Not every AI app. See section 16.6. |
| Component store, hibernation, old drivers, app/dev caches, WSL compact? | **Yes** — section 17 modules (v1.4.0). ResetBase, model weights, and WSL/Docker rows start unchecked. |

For current rules, read README and CONTEXT. Sections 4–14 are the August 2026 backlog. Sections 16 and 17 are the current proposals.

---

## 16. AI tool residue (implemented in v1.4.0)

**Status:** shipped in v1.4.0. Section 16.6 lists providers that are still not on the allowlist.

**Goal:** one Scan shows the local junk from Cursor, Claude, and the other common coding agents, so the user does not hunt `%USERPROFILE%` and `%APPDATA%`. Clean deletes only an allowlist. It does not uninstall the apps, does not walk project repos, and does not touch logins, skills, or settings.

**Why a new module:** `privacy` only flips Windows Copilot / Recall / Paint / Notepad / Edge policy keys. `bloatware` can remove the inbox Copilot Store app. Neither deletes Cursor, Claude Code, Codex, Windsurf, Ollama, or LM Studio files.

### 16.1 Three modules (do not mix them)

Profiles select whole modules. Chat history and model weights must not ride along with a cache wipe.

| Module | ID | Risk | Default | Profiles | Kind |
|--------|----|------|---------|----------|------|
| AI caches & logs | `ai_caches` | Safe | off (`OPT_IN`) | `disk`, `full`, and new `ai` | ephemeral |
| AI chats & sessions | `ai_history` | Moderate | off | new `ai` only. Add to `MANUAL_PRESET_IDS` so **Full** leaves it off | ephemeral (files come back when the app is used again) |
| AI model weights | `ai_models` | Aggressive | off | none. User ticks the module. Each model row starts **Clean? `[ ]`** | sticky until the user re-downloads |

`standard`, `safe`, `privacy`, `oem`, `new_pc`, and `debloat` do not select any of these.

New profile `ai` = `ai_caches` + `ai_history`. GUI intent button **AI tools** next to Free disk / New laptop / Debloat. Model weights stay a separate checkbox because a cache clean must not offer to delete tens of GB unless that module is on, and even then the rows start unchecked.

Add `CleanItem.default_include: bool = True`. GUI row insert uses it for the Clean? mark. Only `ai_models` rows set `default_include=False`. Extra confirm (same idea as Windows.old) when any model row is included: name the tool and the size, say the weights must be downloaded again.

### 16.2 What Clean is allowed to delete

Scan skips a row when the path is missing or size is 0. Honor env overrides before the default home path: `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `COPILOT_HOME`, `COPILOT_CACHE_HOME`. If unset, use the defaults below.

Quit the app first. Locked files stay **Still present** (existing verify). Repercussions must say the app recreates caches, and that history rows forget local chats while project source stays put.

#### Cursor (confirmed on this PC, 2026-10-08)

Install to leave alone: `C:\Program Files\Cursor`.

| Tier | Row id | Path | What it is | This PC |
|------|--------|------|------------|---------|
| Cache | `cursor_roaming_cache` | `%APPDATA%\Cursor\` → `Cache`, `Code Cache`, `GPUCache`, `DawnGraphiteCache`, `DawnWebGPUCache`, `CachedData`, `CachedExtensionVSIXs`, `CachedProfilesData`, `logs`, `Crashpad`, `sentry`, `process-monitor`, `blob_storage` | Electron / shader / version caches and logs. Old `CachedData` folders pile up after updates | CachedData ~335 MB, Cache ~14 MB, logs ~5 MB |
| Cache | `cursor_temp` | `%TEMP%\cursor`, `%TEMP%\cursor-agent-logs-*`, `%TEMP%\cursor-sandbox-cache`, `%TEMP%\cursor-inno-updater-*.log` | Agent logs, sandbox cache, updater logs | present |
| Cache | `cursor_tracking` | `%USERPROFILE%\.cursor\ai-tracking\`, `%USERPROFILE%\.cursor\statsig-cache.json*` | Local code-tracking DB and analytics cache | ai-tracking ~20 MB |
| History | `cursor_global_state` | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` (+ `-shm`, `-wal`) and sibling folders `anysphere.cursor-agent-host`, `anysphere.cursor-agent-worker`, `anysphere.cursor-commits` | Cursor 3+ stores conversation content in the global DB. Delete only these names. Other `globalStorage` extension folders stay | globalStorage ~844 MB |
| History | `cursor_workspace_storage` | `%APPDATA%\Cursor\User\workspaceStorage` | Per-project `state.vscdb` (older chats + workspace UI state such as open editors) | ~1 MB here |
| History | `cursor_dot_projects` | `%USERPROFILE%\.cursor\projects` | Agent transcripts, `agent-tools`, terminal scrollback, `worker.log`. Not the user’s source tree | ~5 MB here |
| History | `cursor_chats` | `%USERPROFILE%\.cursor\chats` | Chat payload folders | ~4 MB |
| History | `cursor_acp_sessions` | `%USERPROFILE%\.cursor\acp-sessions` | ACP / agent session blobs | ~197 MB |
| History | `cursor_plans` | `%USERPROFILE%\.cursor\plans` | Generated plan files | present |
| History | `cursor_agent_stores` | `%LOCALAPPDATA%\Cursor\AgentStores` | Local agent store DBs | ~8 MB |

**Cursor keep list (never a Clean target):**

- `%APPDATA%\Cursor\User\settings.json`, `snippets\`, `keybindings.json` if present
- `%APPDATA%\Cursor\auth.json`, `Local State`, `Preferences` (login / machine id)
- `%USERPROFILE%\.cursor\skills\`, `skills-cursor\`, `agents\`, `plugins\`, `extensions\`
- `%USERPROFILE%\.cursor\argv.json`, `cli-config.json`, `ide_state.json`, `.gitignore`
- Anything inside a git repo (`.cursor\rules`, `.cursorrules`). Do not search the disk for those.

Extensions are re-downloadable but small here (~5 MB) and required for SSH / WSL. Leave them. If a later version wants an extensions row, it stays `default_include=False`.

#### Claude Code and Claude Desktop (not installed here; still ship the allowlist)

Home is `%USERPROFILE%\.claude`, or `CLAUDE_CONFIG_DIR` when set. Official layout: [Explore the .claude directory](https://code.claude.com/docs/en/claude-directory). Delete **children**, never the whole `.claude` tree (that tree holds settings, skills, and credentials).

| Tier | Row id | Delete only these children | Leave in place |
|------|--------|----------------------------|----------------|
| Cache | `claude_cache` | `cache\`, `debug\`, `logs\`, `paste-cache\`, `shell-snapshots\`, `session-env\`, `statsig\`, `todos\` (legacy), `backups\` (old `~/.claude.json` copies; keep the newest file only if easy, otherwise skip `backups\` in v1) | |
| History | `claude_sessions` | `projects\` **except** each project’s `memory\` folder (auto memory is user-facing notes), `history.jsonl`, `file-history\`, `plans\`, `tasks\`, `sessions\`, `image-cache\`, `uploads\`, `usage-data\`, `dev-mods\`, `feedback\`, `feedback-bundles\` | `CLAUDE.md`, `settings.json`, `settings.local.json`, `rules\`, `skills\`, `commands\`, `agents\`, `workflows\`, `output-styles\`, `agent-memory\`, `plugins\`, `keybindings.json`, `themes\`, `.credentials.json` |
| Cache | `claude_temp` | `%TEMP%\claude\` (scratchpads and pasted images; `CLAUDE_CODE_TMPDIR` if set) | |
| Cache | `claude_desktop_cache` | `%APPDATA%\Claude\` and `%LOCALAPPDATA%\AnthropicClaude\` electron caches only: `Cache`, `Code Cache`, `GPUCache`, `DawnGraphiteCache`, `DawnWebGPUCache`, `logs`, `Crashpad` | `Local Storage`, `IndexedDB`, `Session Storage` (those are the desktop chat DB — history row below) |
| History | `claude_desktop_chats` | `Local Storage`, `IndexedDB`, `Session Storage`, `Network` under the same Claude desktop roots, plus a Store package if present: `%LOCALAPPDATA%\Packages\Claude_*` / `Anthropic*Claude*` **LocalState / LocalCache only after the folder name is checked** | Do not delete the package install |

**Never:** `%USERPROFILE%\.claude.json` (OAuth, UI, personal MCP). Project `CLAUDE.md`, `.claude\`, `.mcp.json`. `claude purge` remains the app’s own per-project command; this module is the all-projects wipe.

#### Other coding agents (row appears only if the folder exists)

| Tool | Cache row | History row | Never delete |
|------|-----------|-------------|--------------|
| Codex CLI / Windows app | `%USERPROFILE%\.codex\` logs / cache dirs if present (`CODEX_HOME`) | `sessions\`, session sqlite such as `state_5.sqlite` | `auth.json`, `config.toml` |
| Gemini CLI | `%USERPROFILE%\.gemini\tmp\` | `tmp\*\chats\` (covered by wiping `tmp`) | `settings.json`, `oauth_creds.json`, `mcp-oauth-tokens.json`, `GEMINI.md` |
| GitHub Copilot CLI | `%LOCALAPPDATA%\copilot` (`COPILOT_CACHE_HOME`) | `%USERPROFILE%\.copilot\session-state`, `otel` (`COPILOT_HOME`) | config / login files beside those |
| VS Code Copilot / Cline / Continue | — | only these `globalStorage` folders when present: `github.copilot-chat`, `github.copilot`, `saoudrizwan.claude-dev`, `continue.continue`, `rooveterinaryinc.roo-cline` | the rest of `%APPDATA%\Code` |
| Windsurf / Codeium | `%APPDATA%\Windsurf\` same electron cache names as Cursor | `%USERPROFILE%\.codeium\windsurf\` memories / chat dumps; `%USERPROFILE%\.windsurf` session data if it is not `rules` or `mcp_config.json` | rules, `mcp_config.json`, the install |
| Continue | `%USERPROFILE%\.continue\index` | `%USERPROFILE%\.continue\sessions` | `config.json` |
| Cline | — | `%USERPROFILE%\.cline\` session / `data` state | `settings\cline_mcp_settings.json` |
| Aider | `%USERPROFILE%\.aider*` cache files in the home directory only | — | do not scan drives for `.aider.chat.history.md` |
| ChatGPT desktop | `%APPDATA%\ChatGPT` or `%APPDATA%\com.openai.chat` cache/logs/GPUCache | that app’s `Local Storage` + `IndexedDB` | login `Local State` if it is outside those two folders; when unsure, ship the cache row only |
| JetBrains AI | `%LOCALAPPDATA%\JetBrains\<IDE>\llm-jcp-outbox` and `event-log-metadata\llmc` | — | `options\llm*.xml`, `AIAssistant*.xml` (MCP lists and prompt library), `plugins\ml-llm` |

#### Local model apps (module `ai_models`, rows start unchecked)

| Tool | Logs (put these in `ai_caches`, not models) | Weights row | Never delete |
|------|-----------------------------------------------|-------------|--------------|
| Ollama | `%LOCALAPPDATA%\Ollama\*.log`, `upgrade.log` | `%USERPROFILE%\.ollama\models` | `%LOCALAPPDATA%\Programs\Ollama`, `.ollama\id_ed25519`, `id_ed25519.pub`, `config.json` |
| LM Studio | `%APPDATA%\LM Studio\` electron caches/logs; `%USERPROFILE%\.lmstudio\server-logs` | `%USERPROFILE%\.lmstudio\models` and `hub` model blobs | `credentials\`, `settings.json`, `mcp.json`, `extensions\`, `config-presets\`, `C:\Program Files\LM Studio` |
| LM Studio chats | — | history module row: `.lmstudio\conversations` | `user-files\`, `projects\` |

On this PC, Ollama weights were ~33 GB and LM Studio weights ~2.4 GB. That is why they are a separate module with an extra confirm.

### 16.3 Implementation map (when approved)

| Change | Where |
|--------|--------|
| Allowlists + scan/clean | `modules/ai_caches.py`, `modules/ai_history.py`, `modules/ai_models.py`. Copy the path/size/`clear_directory_contents` pattern from `modules/tracking.py`. One walk per clean, no second size pass |
| Register + opt-in | `modules/__init__.py`: `all_modules()`, `OPT_IN_MODULE_IDS`. `ai_history` and `ai_models` also in `MANUAL_PRESET_IDS` |
| Profiles | `cleaner.py` `select_modules`: add `disk` ids `ai_caches`; add profile `ai`. `full` already excludes `MANUAL_PRESET_IDS` |
| Status | `utils/item_status.py`: all three `ephemeral` except `ai_models` = `sticky`. Not in `ADMIN_MODULES` (user-profile files) |
| Copy | `modules/item_info.py` effect + repercussions per row id |
| GUI | `ui/gui.py` `PROFILE_IDS` + intent button **AI tools**. `default_include`. Model confirm next to the Windows.old confirm |
| CLI | `ui/cli.py` profile help text only if profiles are listed there |
| Tests | `tests/test_smoke.py`: module ids exist; allowlist paths do not contain `Program Files`, `auth.json`, `.credentials.json`, `settings.json`, `skills`, `id_ed25519`; missing paths produce no items (tmp home) |
| Docs | `README.md` module table + profile line, `CONTEXT.md` module ids / do-not list, `CHANGELOG.md` when it ships. Version bump in `__init__.py` |

Clean implementation notes:

- Delete listed children, then leave the parent (so Claude settings and Cursor `User\` survive).
- Glob only the documented prefixes (`cursor-agent-logs-*`, `cursor-inno-updater-*.log`, `Packages\Claude_*`). No broad AppData search.
- `path_size` already caps huge trees; model rows can report the real size because users need it for the confirm. If the cap would under-report multi-GB weights, size model folders with a dedicated walk or raise the cap for that row only.
- Do not add these paths to `temp_files` or `tracking`. A buried row is how a Standard clean would wipe chats by accident.

### 16.4 Out of scope

- Uninstalling Cursor, Claude, Ollama, LM Studio, or VS Code
- Cloud chats (claude.ai, ChatGPT.com, Cursor account sync). This is local disk only
- Windows Copilot / Recall policies (already in `privacy`)
- Repo files: `CLAUDE.md`, `.claude\`, `.cursor\rules`, `AGENTS.md`
- Wiping every JetBrains cache. Only the AI outbox / `llmc` metadata
- Reading file contents during Scan (transcripts contain pasted secrets)

### 16.5 Done when

- [ ] Scan with nothing installed shows no AI rows
- [ ] Scan on a machine with Cursor lists cache and history as separate rows with sizes
- [ ] Dry-run prints the paths and deletes nothing
- [ ] Clean of `ai_caches` leaves `%APPDATA%\Cursor\User\settings.json` and `%USERPROFILE%\.cursor\skills`
- [ ] Clean of `ai_history` leaves `.claude.json` / `.credentials.json` / `settings.json` when those files exist
- [ ] `ai_models` rows start as `[ ]` and Clean refuses them until the extra confirm
- [ ] `--profile standard` and `--profile full` do not select `ai_history` or `ai_models`
- [ ] `--profile disk` selects `ai_caches` and not `ai_history` or `ai_models` (section 17 may also add `dev_caches` and `app_caches` to `disk`)
- [ ] `--profile ai` selects caches + history
- [ ] Re-scan after Clean shows **Fixed** for removed rows, **Still present** if the app had a file lock

### 16.6 Providers not in v1

Section 16 is a **named allowlist**. A row appears only when that app’s folder exists. Scan does not search the disk for “AI.” Cloud chats stay in the cloud.

**v1 includes these local cache writers:**

| Kind | Apps | What is cleaned |
|------|------|-----------------|
| Online clients (local files only) | Cursor, Claude Code, Claude Desktop, Codex CLI / Codex app, Gemini CLI, GitHub Copilot CLI, VS Code Copilot, Cline, Continue, Roo, Windsurf / Codeium, Aider, ChatGPT desktop, JetBrains AI Assistant | Caches and logs in `ai_caches`. Chats in `ai_history` where a path is listed in 16.2. |
| Offline runners | Ollama, LM Studio | Logs and electron caches in `ai_caches`. LM Studio conversations in `ai_history`. Weights in `ai_models`, each row starting unchecked. |

**Not in v1.** Add later as more allowlist rows, same three modules. Do not add a filesystem search.

| Kind | Apps | Where the row belongs |
|------|------|------------------------|
| Other coding tools | Amazon Q, Tabnine, Sourcegraph Cody, Augment, Zed, Trae, Pieces, Supermaven | `ai_caches` / `ai_history`, with the same keep-list rule (no login, no settings) |
| Other local runners | Jan, GPT4All, llama.cpp, koboldcpp, AnythingLLM, Open WebUI | logs in `ai_caches`; weight folders in `ai_models` |
| Shared weight cache | Hugging Face hub (`%USERPROFILE%\.cache\huggingface`) | `ai_models` only (unchecked, extra confirm) |
| Image / video weights | ComfyUI, Stable Diffusion, Forge, InvokeAI | `ai_models` only |

---

## 17. Large-disk reclaim (implemented in v1.4.0)

**Status:** shipped in v1.4.0.

**Goal:** Scan shows the folders and Windows stores that actually hold tens of GB, then Clean deletes an allowlist. This shipped as `system_reclaim`, `driver_store`, `app_caches`, `dev_caches`, `dev_disks`, `windows_features`, and `browser_privacy`, plus the wider browser cache profiles.

Stay on the existing pipeline: size on Scan, Dry-run, Clean, verify re-scan. Slow or one-way actions stay opt-in and out of **safe** and **standard**.

### 17.1 System reclaim (`system_reclaim`)

New module. Risk aggressive. `default_enabled=False`. Not in `safe`, `standard`, or `full`. User ticks the module, or a later **workstation** / advanced preset lists it explicitly. Admin. Each row shows a byte size before Clean.

| Row id | Scan | Clean | Notes |
|--------|------|-------|-------|
| `component_store` | `Dism /Online /Cleanup-Image /AnalyzeComponentStore` | `Dism /Online /Cleanup-Image /StartComponentCleanup` | Superseded update files. Slow. |
| `component_store_resetbase` | same analysis, separate row | add `/ResetBase` | Starts as **Clean? `[ ]`**. Extra confirm: Windows can no longer uninstall those updates. |
| `hiberfil` | `powercfg /a` and size of `hiberfil.sys` | `powercfg -h off` | Often most of installed RAM. Say on the row that Fast Startup turns off too. |
| `shadow_copies` | `vssadmin list shadowstorage` | shrink the cap | Do not delete every restore point from this row. |
| `upgrade_leftovers` | `C:\$Windows.~BT`, `C:\$Windows.~WS` | delete only those setup folders | Same family as `Windows.old`. |

`/ResetBase` and “delete every restore point” stay off even when the module is selected. A wipe-all shadow row, if ever added, is its own unchecked row with a Windows.old-style confirm.

### 17.2 Driver Store (`driver_store`)

`C:\Windows\System32\DriverStore\FileRepository` is commonly 10–30 GB on OEM PCs. `bloatware_oem` removes SupportAssist / Vantage / Wolf. This module removes the driver copies those tools left behind.

- Scan: `pnputil /enum-drivers`. One row per published `oem*.inf` that is not the driver currently in use. Name the provider and the date.
- Clean: `pnputil /delete-driver oemN.inf /uninstall` only for those superseded packages.
- First ship can be scan-only if delete is not trustworthy yet. Delete lands in a follow-up once the row text is obvious.
- Opt-in, Admin, not in `safe` / `standard` / `full`.

### 17.3 App caches (`app_caches`) and wider browser caches

`app_caches`: Safe, `default_enabled=True` once the allowlist is tight, included in `disk` and `full`. Electron and launcher caches only. Leave `Local Storage` and `IndexedDB` so logins survive (same rule as Cursor cache rows in section 16).

| Target | Delete | Leave |
|--------|--------|-------|
| Discord, Slack, Zoom, Spotify, new Teams | `Cache`, `Code Cache`, `GPUCache`, logs | login DBs, the install |
| Steam | `shadercache`, leftover download staging | `steamapps\common`, save games |
| Epic, Battle.net | web cache | the game install |
| `C:\NVIDIA`, `C:\AMD`, `C:\Intel` | extracted driver setup folders at the drive root | `C:\Program Files\NVIDIA`, `C:\Program Files\AMD`, `C:\Program Files\Intel` |

`browser_caches` today is Edge, Chrome, and Firefox **Default** only. Extend it to Profile 1, Profile 2, Brave, Opera, and Vivaldi, still cache folders only.

Cookies and history are a different module, `browser_privacy` (Moderate, opt-in, not in `disk`). They log people out of sites.

### 17.4 Developer caches and disks

Sits beside section 16. A cache clean must not be one checkbox away from deleting Ollama weights or a WSL distro.

| Module | ID | Default | Profiles | Rows | Leave alone |
|--------|----|---------|----------|------|-------------|
| Dev tool caches | `dev_caches` | on in `disk`, `full`, and new `workstation` | those | npm cache, pip cache, NuGet HTTP cache, Gradle caches, Go build cache, Yarn/pnpm store, Cargo `git` checkouts | project folders, `node_modules`, Cargo registry sources, editor settings |
| Dev disks | `dev_disks` | off; every row `default_include=False` | none until the user ticks the module | `docker system prune` of build cache; WSL `ext4.vhdx` compact (`wsl --shutdown`, then compact that one disk) | images the user did not include, the distro itself, files under `\\wsl$` |

WSL compact is often the largest reclaim on a machine that has used Docker or a distro for a year. Scan shows the VHDX size and says the distro is not deleted. Compact can take a long time. If a process holds the file, verify stays **Still present**.

New profile `workstation` = `disk` modules + `dev_caches` + `ai_caches`. It does not select `ai_history`, `ai_models`, `dev_disks`, `system_reclaim`, or `driver_store`.

### 17.5 Languages and optional features (`windows_features`)

`Get-WindowsCapability -Online` for extra language packs and features on demand. Remove a language only when it is neither the current user language nor the system UI language.

Optional-feature rows worth shipping: XPS, Steps Recorder, Windows Media Player legacy.

Leave SMB1 decisions, .NET, and Hyper-V alone. Opt-in. Included when the user picks **debloat**, not in `standard`.

### 17.6 Product glue

These make the modules above usable. They are not extra cleanup targets.

| Item | Behavior |
|------|----------|
| Size summary | Above the results table, sum bytes of checked rows by Safe / Moderate / Aggressive. The table already has the sizes. |
| Undo for startup and services | Privacy already records previous DWORD values. Record Run-key values and service start types (`auto`, `demand`, `disabled`) the same way. AppX, winget, driver, and DISM rows stay one-way; the row text says so. |
| Scheduled Free disk | A Task Scheduler entry that runs the CLI with `--profile disk`. Still an on-demand clean, not a resident optimizer. Add it after `app_caches` and `dev_caches` exist, because those folders refill. |

### 17.7 Out of scope

- Registry “cleaner” that deletes orphan keys
- RAM booster, memory optimizer, or SSD defrag
- Whole-disk duplicate finder
- General Win32 uninstaller
- WinDirStat-style scan of every folder on the drive
- Defender, Windows Update, Edge removal, BitLocker (existing non-goals)
- Turning SysMain / WSearch disable on inside `standard`

### 17.8 Implementation map (when approved)

| Change | Where |
|--------|--------|
| Component store, hibernation, shadow cap, upgrade leftovers | `modules/system_reclaim.py` |
| Superseded drivers | `modules/driver_store.py` |
| Chat / launcher / driver-extract caches | `modules/app_caches.py`; extra browser profiles in `modules/browser_caches.py` |
| Site cookies / history | `modules/browser_privacy.py` (separate, opt-in) |
| npm / pip / NuGet / Gradle / Go / Cargo git | `modules/dev_caches.py` |
| Docker prune, WSL compact | `modules/dev_disks.py` |
| Language packs, XPS, Steps Recorder, legacy WMP | `modules/windows_features.py` |
| Register + profiles | `modules/__init__.py`, `cleaner.py` `select_modules`. `system_reclaim`, `driver_store`, `dev_disks` in `OPT_IN_MODULE_IDS` and `MANUAL_PRESET_IDS`. `windows_features` opt-in, selected by `debloat` only. |
| Size summary, startup/service undo, schedule | `ui/gui.py`, `utils/privacy_undo.py` or a sibling undo store, CLI flag for the scheduled command |
| Copy, status, tests, docs | `item_info.py`, `item_status.py`, `tests/test_smoke.py`, README, CONTEXT, CHANGELOG on ship |

`system_reclaim` and `driver_store` need Admin and belong in `ADMIN_MODULES`. `dev_disks` is user-profile / local service, not a registry policy.

### 17.9 Suggested order

1. `system_reclaim` without `/ResetBase` auto-checked, plus the GB summary
2. `driver_store` scan, then delete
3. `app_caches` and extra browser profiles
4. `dev_caches`, WSL compact, and section 16 together as the workstation piece
5. `windows_features`, then a scheduled `--profile disk` task

### 17.10 Done when

- [ ] Scan shows a byte size for the component store, `hiberfil.sys` when present, and each upgrade-leftover folder
- [ ] Dry-run of `system_reclaim` runs no DISM cleanup and does not call `powercfg -h off`
- [ ] `/ResetBase` stays unchecked until the extra confirm
- [ ] Driver rows list superseded packages only; the in-use driver is absent
- [ ] `app_caches` leaves Discord/Slack/Teams login databases in place
- [ ] `browser_caches` still does not delete cookies
- [ ] `--profile disk` selects `dev_caches` and does not select `dev_disks`, `ai_history`, or `ai_models`
- [ ] WSL compact row states the distro is kept, and starts unchecked
- [ ] `windows_features` does not offer the current UI language
- [ ] Checked-row GB totals match the table
- [ ] No Defender, Windows Update, or in-use driver package is a Clean target
