# Windows Cleaner — Improvement Plan

**For review before implementation.**  
Project: `C:\Custom\Projects\PycharmProjects\windowscleaner`  
Date: 2026-08-02  
Sources: current codebase, CONTEXT.md / README, Win11Debloat (2026), WinUtil / ShutUp10-style guides, OEM debloat practices

---

## 1. Goal of this document

List **everything worth considering** so you can approve, cut, or reorder work.  
Nothing here is implemented until you say so.

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
[ ] Phase E — Git basics (LICENSE, changelog, init)  → LATER
[ ] Phase E+ — pyproject + tests                     → LATER
[x] Phase E++ — GitHub Actions + Release zip  → SKIPPED (manual upload)

Release process: .\build.ps1 locally → upload zip/EXE to GitHub Release yourself
UI declutter module: no (skipped — dilutes cleaner focus)
```

---

## 15. Bottom line

| Question | Answer |
|----------|--------|
| All slow-making registry keys today? | **No** — strong privacy/telemetry set; room for AI + companion keys |
| Optional bloatware scan/remove today? | **Yes** — AppX allowlist, opt-in; incomplete vs Win11Debloat + no provisioned/OEM Win32 |
| Highest ROI next? | **Phase A + B** (AI policies + provisioned AppX) |
| Biggest “real PC feels faster” gap? | **OEM Win32** (Phase C) — separate, aggressive, opt-in |
| Git/prod? | Ready for **Phase E** anytime; independent of cleanup power |

Review this file, tick Section 14, then ask to implement the approved phases only.
