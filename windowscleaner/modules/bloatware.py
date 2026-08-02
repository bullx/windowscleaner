"""Remove common preinstalled / Store bloatware AppX packages (installed + provisioned)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk


@dataclass(frozen=True)
class BloatApp:
    """Substring matched against PackageFamilyName / Name / PackageName."""

    match: str
    label: str
    reason: str


# Intentionally conservative core + Win11Debloat 2026 defaults.
# Xbox / Store / Photos / Calculator / Terminal / HEVC are NOT listed as must-remove.
BLOAT: list[BloatApp] = [
    BloatApp("Microsoft.549981C3F5F10", "Cortana", "Deprecated assistant."),
    BloatApp("Microsoft.BingNews", "News", "News feed / engagement app."),
    BloatApp("Microsoft.BingWeather", "Weather", "Optional; web does the same."),
    BloatApp("Microsoft.BingFinance", "Finance", "Optional Bing finance."),
    BloatApp("Microsoft.BingSports", "Sports", "Optional Bing sports."),
    BloatApp("Microsoft.BingSearch", "Bing Search", "Bing search package."),
    BloatApp("Microsoft.GetHelp", "Get Help", "Support funnel app."),
    BloatApp("Microsoft.Getstarted", "Tips / Get Started", "Tips & suggestions."),
    BloatApp("Microsoft.MicrosoftOfficeHub", "Office Hub", "Office upsell hub."),
    BloatApp("Microsoft.MicrosoftSolitaireCollection", "Solitaire Collection", "Game + ads."),
    BloatApp("Microsoft.MicrosoftStickyNotes", "Sticky Notes", "Optional notes app."),
    BloatApp("Microsoft.PowerAutomateDesktop", "Power Automate", "RPA upsell; rarely needed."),
    BloatApp("Microsoft.SkypeApp", "Skype", "Legacy chat client."),
    BloatApp("Microsoft.People", "People", "Contacts hub seldom used."),
    BloatApp("Microsoft.WindowsFeedbackHub", "Feedback Hub", "Feedback / telemetry UI."),
    BloatApp("Microsoft.WindowsMaps", "Maps", "Optional maps client."),
    BloatApp("Microsoft.WindowsSoundRecorder", "Sound Recorder", "Optional; Voice Recorder may remain."),
    BloatApp("Microsoft.ZuneMusic", "Groove Music / Media Player legacy", "Legacy Zune music."),
    BloatApp("Microsoft.ZuneVideo", "Films & TV / Zune Video", "Legacy video storefront."),
    BloatApp("Microsoft.YourPhone", "Phone Link", "Optional cross-device bridge."),
    BloatApp("MicrosoftWindows.Client.WebExperience", "Widgets / Web Experience", "News widgets feed."),
    BloatApp("Microsoft.Todos", "Microsoft To Do", "Optional task app."),
    BloatApp("Microsoft.Messaging", "Messaging", "Legacy SMS bridge."),
    BloatApp("Microsoft.OneConnect", "Paid Wi-Fi & Cellular", "Mobile plans upsell."),
    BloatApp("Microsoft.MixedReality.Portal", "Mixed Reality Portal", "VR portal unused on most PCs."),
    BloatApp("Microsoft.Microsoft3DViewer", "3D Viewer", "Rarely needed."),
    BloatApp("Microsoft.Print3D", "Print 3D", "3D printing upsell."),
    BloatApp("Microsoft.Wallet", "Pays / Wallet", "Deprecated payments."),
    BloatApp("Clipchamp.Clipchamp", "Clipchamp", "Video editor upsell."),
    BloatApp("Microsoft.OutlookForWindows", "Outlook (new)", "New Outlook consumer app."),
    BloatApp("MicrosoftTeams", "Teams (personal)", "Consumer Teams - keep if you use it."),
    BloatApp("MSTeams", "Teams", "Teams package variant."),
    BloatApp("microsoft.windowscommunicationsapps", "Mail and Calendar", "Legacy Mail/Calendar."),
    BloatApp("Microsoft.GamingApp", "Xbox app", "Xbox PC app - keep if you game."),
    BloatApp("Microsoft.Xbox.TCUI", "Xbox TCUI", "Xbox UI helper."),
    BloatApp("Microsoft.XboxGameOverlay", "Xbox Game Overlay", "Xbox overlay."),
    BloatApp("Microsoft.XboxGamingOverlay", "Xbox Gaming Overlay", "Game Bar companion."),
    BloatApp("Microsoft.XboxIdentityProvider", "Xbox Identity Provider", "Xbox auth helper."),
    BloatApp("Microsoft.XboxSpeechToTextOverlay", "Xbox Speech Overlay", "Xbox speech overlay."),
    BloatApp("Microsoft.XboxApp", "Xbox Console Companion", "Legacy Xbox app."),
    BloatApp("King.com.CandyCrushSaga", "Candy Crush Saga", "OEM/Store game junk."),
    BloatApp("King.com.CandyCrushSodaSaga", "Candy Crush Soda", "OEM/Store game junk."),
    BloatApp("King.com.BubbleWitch3Saga", "Bubble Witch 3", "OEM/Store game junk."),
    BloatApp("king.com.CandyCrushFriends", "Candy Crush Friends", "OEM/Store game junk."),
    BloatApp("Disney.37853FC22B2CE", "Disney+", "Streaming upsell."),
    BloatApp("SpotifyAB.SpotifyMusic", "Spotify", "OEM Spotify stub."),
    BloatApp("PandoraMediaInc", "Pandora", "OEM music stub."),
    BloatApp("Facebook.Facebook", "Facebook", "OEM social stub."),
    BloatApp("FACEBOOK.FACEBOOK", "Facebook (alt id)", "OEM social stub."),
    BloatApp("Instagram", "Instagram", "OEM social stub."),
    BloatApp("Facebook.Instagram", "Instagram (Facebook)", "OEM social stub."),
    BloatApp("Netflix", "Netflix", "OEM streaming stub."),
    BloatApp("4DF9E0F8.Netflix", "Netflix (Store id)", "OEM streaming stub."),
    BloatApp("Amazon.com.Amazon", "Amazon", "OEM shopping stub."),
    BloatApp("BytedancePte.Ltd.TikTok", "TikTok", "OEM social stub."),
    BloatApp("EclipseManager", "Eclipse Manager", "OEM bloat."),
    BloatApp("ActiproSoftwareLLC", "Actipro", "OEM bloat."),
    BloatApp("AdobeSystemsIncorporated.AdobePhotoshopExpress", "Photoshop Express", "OEM trial."),
    BloatApp("DolbyLaboratories.DolbyAccess", "Dolby Access", "OEM audio upsell."),
    BloatApp("Microsoft.Advertising.Xaml", "Advertising XAML", "Ad framework package."),
    BloatApp("XP9CXNGPPJ97XX", "Microsoft Copilot", "Win11Debloat default: Copilot AI assistant."),
    BloatApp("Microsoft.Copilot", "Copilot (Store)", "Copilot Store package variant."),
    BloatApp("Microsoft.Windows.AIHub", "Copilot+ AI Hub", "Win11Debloat: AI Hub on 24H2+."),
    BloatApp("Microsoft.Windows.DevHome", "Dev Home", "Win11Debloat: discontinued Dev Home."),
    BloatApp("Microsoft.StartExperiencesApp", "Start Experiences / Widgets feed", "Powers Widgets My Feed."),
    BloatApp("Microsoft.WidgetsPlatformRuntime", "Widgets Platform Runtime", "Widgets runtime package."),
    BloatApp("MicrosoftCorporationII.QuickAssist", "Quick Assist", "Remote assist upsell / bloat."),
    BloatApp("MicrosoftCorporationII.MicrosoftFamily", "Family Safety", "Family Safety consumer app."),
    BloatApp("Microsoft.PCManager", "Microsoft PC Manager", "Microsoft cleanup upsell app."),
    BloatApp("Microsoft.BingFoodAndDrink", "Bing Food And Drink", "Discontinued Bing lifestyle app."),
    BloatApp("Microsoft.BingHealthAndFitness", "Bing Health And Fitness", "Discontinued Bing lifestyle app."),
    BloatApp("Microsoft.BingTranslator", "Bing Translator", "Optional Bing translator."),
    BloatApp("Microsoft.BingTravel", "Bing Travel", "Discontinued Bing travel."),
    BloatApp("Microsoft.News", "Microsoft News", "News aggregator / Start feed app."),
    BloatApp("Microsoft.NetworkSpeedTest", "Network Speed Test", "Seldom-needed UWP speed test."),
    BloatApp("Microsoft.MicrosoftJournal", "Microsoft Journal", "Optional pen journal."),
    BloatApp("Microsoft.Office.Sway", "Sway", "Legacy Sway presentation app."),
    BloatApp("Microsoft.3DBuilder", "3D Builder", "Legacy 3D Builder."),
    BloatApp("LinkedInforWindows", "LinkedIn", "OEM LinkedIn stub."),
    BloatApp("AmazonVideo.PrimeVideo", "Prime Video", "OEM streaming stub."),
    # Win11Debloat default gaps
    BloatApp("Microsoft.WindowsAlarms", "Alarms & Clock", "Optional; many users keep — review before Clean."),
    BloatApp("Microsoft.Office.OneNote", "OneNote (UWP)", "Store OneNote; keep if you use it."),
    BloatApp("Microsoft.MicrosoftPowerBIForWindows", "Power BI", "Business analytics client rarely needed."),
    BloatApp("Microsoft.Whiteboard", "Microsoft Whiteboard", "Optional whiteboard app."),
    BloatApp("Microsoft.Windows.Photos.MediaFileTranscoder", "Photos transcoder helper", "Optional Photos helper (not Photos app)."),
    # Third-party candy (Win11Debloat defaults)
    BloatApp("Asphalt8Airborne", "Asphalt 8", "OEM racing game junk."),
    BloatApp("COOKINGFEVER", "Cooking Fever", "OEM game junk."),
    BloatApp("FarmVille2CountryEscape", "FarmVille 2", "OEM game junk."),
    BloatApp("HiddenCity", "Hidden City", "OEM game junk."),
    BloatApp("MarchofEmpires", "March of Empires", "OEM game junk."),
    BloatApp("flaregamesGmbH.RoyalRevolt", "Royal Revolt", "OEM game junk."),
    BloatApp("CaesarsSlotsFreeCasino", "Caesars Slots", "OEM casino junk."),
    BloatApp("DisneyMagicKingdoms", "Disney Magic Kingdoms", "OEM game junk."),
    BloatApp("HULULLC.HULUPLUS", "Hulu", "OEM streaming stub."),
    BloatApp("SlingTV", "Sling TV", "OEM streaming stub."),
    BloatApp("iHeartRadio", "iHeartRadio", "OEM radio stub."),
    BloatApp("TuneInRadio", "TuneIn Radio", "OEM radio stub."),
    BloatApp("Duolingo-LearnLanguagesforFree", "Duolingo", "OEM learning stub."),
    BloatApp("Flipboard", "Flipboard", "OEM news stub."),
    BloatApp("PicsArt-PhotoStudio", "PicsArt", "OEM photo editor trial."),
    BloatApp("WinZipUniversal", "WinZip UWP", "OEM compression upsell."),
    BloatApp("ACGMediaPlayer", "ACG Media Player", "OEM media player."),
    BloatApp("AutodeskSketchBook", "Autodesk SketchBook", "OEM drawing stub."),
    BloatApp("CyberLinkMediaSuiteEssentials", "CyberLink Media Suite", "OEM multimedia suite."),
    BloatApp("DrawboardPDF", "Drawboard PDF", "OEM PDF stub."),
    BloatApp("NYTCrossword", "NYT Crossword", "OEM puzzle stub."),
    BloatApp("OneCalendar", "One Calendar", "OEM calendar stub."),
    BloatApp("PhototasticCollage", "Phototastic Collage", "OEM collage stub."),
    BloatApp("PolarrPhotoEditorAcademicEdition", "Polarr Photo Editor", "OEM photo editor."),
    BloatApp("Sidia.LiveWallpaper", "Live Wallpaper", "OEM live wallpaper."),
]


def _run_ps(script: str) -> subprocess.CompletedProcess[str]:
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NoLogo",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=flags,
    )


def _parse_json_list(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _list_installed_packages() -> list[dict]:
    from windowscleaner.utils.admin import is_admin

    scripts = [
        "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress"
    ]
    if is_admin():
        scripts.insert(
            0,
            "Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress",
        )

    for script in scripts:
        proc = _run_ps(script)
        if proc.returncode != 0:
            continue
        pkgs = _parse_json_list(proc.stdout)
        if pkgs:
            return pkgs
    return []


def _list_provisioned_packages() -> list[dict]:
    """Packages staged for new users (Admin / DISM view)."""
    from windowscleaner.utils.admin import is_admin

    if not is_admin():
        # Still try — may fail; caller handles empty
        pass
    script = (
        "Get-AppxProvisionedPackage -Online | "
        "Select-Object DisplayName, PackageName, PackageFamilyName | ConvertTo-Json -Compress"
    )
    proc = _run_ps(script)
    if proc.returncode != 0:
        return []
    return _parse_json_list(proc.stdout)


def _matches(pkg: dict, pattern: str) -> bool:
    name = str(pkg.get("Name") or pkg.get("DisplayName") or "")
    family = str(pkg.get("PackageFamilyName") or "")
    full = str(pkg.get("PackageFullName") or pkg.get("PackageName") or "")
    hay = f"{name}|{family}|{full}".lower()
    needle = pattern.lower().replace("*", "")
    if "*" in pattern:
        parts = [p for p in pattern.lower().split("*") if p]
        return all(p in hay for p in parts)
    return needle in hay


def _match_bloat(pkg: dict) -> BloatApp | None:
    for bloat in BLOAT:
        if _matches(pkg, bloat.match):
            return bloat
    return None


class BloatwareModule(CleanModule):
    id = "bloatware"
    label = "Preinstalled Bloatware"
    description = (
        "Removes common Store / OEM junk (Candy Crush, Cortana, Feedback Hub, "
        "News/Weather stubs, Clipchamp, Copilot, trial apps, etc.) and deprovisions "
        "matched packages so they do not return for new users. Xbox packages are "
        "listed but optional in spirit — review the scan before cleaning. "
        "Does not touch Store, Photos, Calculator, or Defender."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = True
    default_enabled = False  # opt-in: uninstalling apps is irreversible without Store reinstall

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        if progress:
            progress("Enumerating installed AppX packages...")
        installed = _list_installed_packages()
        if progress:
            progress("Enumerating provisioned AppX packages...")
        provisioned = _list_provisioned_packages()

        seen_installed: set[str] = set()
        seen_provisioned: set[str] = set()

        for pkg in installed:
            full = str(pkg.get("PackageFullName") or "")
            if not full or full in seen_installed:
                continue
            bloat = _match_bloat(pkg)
            if not bloat:
                continue
            seen_installed.add(full)
            result.items.append(
                CleanItem(
                    id=f"installed:{full}",
                    label=bloat.label,
                    detail=f"Installed — {pkg.get('Name')} — {bloat.reason}",
                    bytes_estimate=0,
                    requires_admin=True,
                    effect=f"Uninstalls installed AppX: {bloat.label}.",
                    repercussions=(
                        "Removed for current/all users until reinstalled from Microsoft Store. "
                        "App data for it is lost."
                    ),
                )
            )

        for pkg in provisioned:
            pname = str(pkg.get("PackageName") or "")
            if not pname or pname in seen_provisioned:
                continue
            bloat = _match_bloat(pkg)
            if not bloat:
                continue
            seen_provisioned.add(pname)
            result.items.append(
                CleanItem(
                    id=f"provisioned:{pname}",
                    label=f"{bloat.label} (provisioned)",
                    detail=(
                        f"Provisioned — {pkg.get('DisplayName') or pname} — {bloat.reason}. "
                        "Stays in the image for NEW users until deprovisioned."
                    ),
                    bytes_estimate=0,
                    requires_admin=True,
                    effect=f"Deprovisions AppX so new users do not get: {bloat.label}.",
                    repercussions=(
                        "Stops reappearing for new local users / some resets. "
                        "Already-installed copies still need the Installed row removed."
                    ),
                )
            )

        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        result = self.scan(progress)
        result.dry_run = dry_run
        admin = is_admin()

        for item in result.items:
            if progress:
                progress(f"{'Would remove' if dry_run else 'Removing'} {item.label}")
            if dry_run:
                result.actions.append(f"Would remove {item.id}")
                continue
            if not admin:
                item.detail = "Needs Administrator - not removed (will show again on Scan)"
                item.repercussions = "Run Restart as Administrator, then Clean again."
                result.errors.append(f"{item.id}: needs Administrator")
                continue

            if item.id.startswith("provisioned:"):
                pname = item.id.split(":", 1)[1].replace("'", "''")
                script = (
                    f"$p = Get-AppxProvisionedPackage -Online | "
                    f"Where-Object {{ $_.PackageName -eq '{pname}' }}; "
                    f"if ($p) {{ $p | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue }}; "
                    f"'DONE'"
                )
                proc = _run_ps(script)
                if proc.returncode == 0:
                    result.actions.append(f"Deprovisioned {item.label} ({pname})")
                else:
                    err = proc.stderr.strip() or proc.stdout.strip() or "failed"
                    result.errors.append(f"{item.label}: {err}")
                continue

            # installed:
            full = item.id.split(":", 1)[1].replace("'", "''")
            script = (
                f"Get-AppxPackage -AllUsers | "
                f"Where-Object {{ $_.PackageFullName -eq '{full}' }} | "
                f"Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue; "
                f"Get-AppxPackage | "
                f"Where-Object {{ $_.PackageFullName -eq '{full}' }} | "
                f"Remove-AppxPackage -ErrorAction SilentlyContinue; "
                f"'DONE'"
            )
            proc = _run_ps(script)
            if proc.returncode == 0:
                result.actions.append(f"Removed {item.label} ({full})")
            else:
                err = proc.stderr.strip() or proc.stdout.strip() or "failed"
                result.errors.append(f"{item.label}: {err}")

        return result
