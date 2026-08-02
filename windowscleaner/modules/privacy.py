"""Privacy & telemetry hardening via registry (and a few policy keys)."""

from __future__ import annotations

import winreg
from dataclasses import dataclass

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk
from windowscleaner.utils.registry import RegChange, get_value, set_dword, values_match


def _windows_edition() -> str:
    """Best-effort ProductName (e.g. Windows 11 Home)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        ) as key:
            name, _ = winreg.QueryValueEx(key, "ProductName")
            return str(name)
    except OSError:
        return ""


def _edition_note(setting_id: str) -> str:
    if setting_id not in {"telemetry_level", "telemetry_dual", "max_telemetry_allowed"}:
        return ""
    edition = _windows_edition().lower()
    if "home" in edition:
        return (
            " Note: on Windows Home, Microsoft may still enforce Required diagnostic "
            "data even when this policy is 0 — Scan/Clean still apply the key."
        )
    return ""


@dataclass(frozen=True)
class PrivacySetting:
    id: str
    label: str
    hive: str
    path: str
    name: str
    desired: int
    description: str


# Curated, well-known privacy toggles. Values match common "debloat" guidance
# for Windows 10/11 without breaking Windows Update or Store authenticity.
SETTINGS: list[PrivacySetting] = [
    PrivacySetting(
        id="telemetry_level",
        label="Diagnostic data -> Security / Required only",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        name="AllowTelemetry",
        desired=0,  # 0=Security (Enterprise/Edu) / effectively minimal on Pro
        description="Caps Windows diagnostic telemetry.",
    ),
    PrivacySetting(
        id="diagtrack_consent",
        label="Disable tailored experiences from diagnostics",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Privacy",
        name="TailoredExperiencesWithDiagnosticDataEnabled",
        desired=0,
        description="Turns off tailored experiences from diagnostic data.",
    ),
    PrivacySetting(
        id="advertising_id",
        label="Disable Advertising ID",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        name="Enabled",
        desired=0,
        description="Stops apps using your advertising ID.",
    ),
    PrivacySetting(
        id="activity_history_publish",
        label="Disable Activity History publish",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\System",
        name="PublishUserActivities",
        desired=0,
        description="Stops publishing activities to Timeline / Microsoft account.",
    ),
    PrivacySetting(
        id="activity_history_upload",
        label="Disable Activity History upload",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\System",
        name="UploadUserActivities",
        desired=0,
        description="Stops uploading activity history to the cloud.",
    ),
    PrivacySetting(
        id="activity_feed",
        label="Disable Activity Feed",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\System",
        name="EnableActivityFeed",
        desired=0,
        description="Disables the activity feed feature.",
    ),
    PrivacySetting(
        id="cortana",
        label="Disable Cortana",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
        name="AllowCortana",
        desired=0,
        description="Policy-disables Cortana.",
    ),
    PrivacySetting(
        id="web_search",
        label="Disable web search in Start",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
        name="DisableWebSearch",
        desired=1,
        description="Keeps Start search local.",
    ),
    PrivacySetting(
        id="bing_search",
        label="Disable Bing search highlights",
        hive="HKCU",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Explorer",
        name="DisableSearchBoxSuggestions",
        desired=1,
        description="Removes Bing suggestions from the search box.",
    ),
    PrivacySetting(
        id="feedback",
        label="Never prompt for feedback",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Siuf\Rules",
        name="NumberOfSIUFInPeriod",
        desired=0,
        description="Stops Feedback Hub nag prompts.",
    ),
    PrivacySetting(
        id="feedback_period",
        label="Feedback sampling period -> 0",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Siuf\Rules",
        name="PeriodInNanoSeconds",
        desired=0,
        description="Companion key for feedback prompts.",
    ),
    PrivacySetting(
        id="tips",
        label="Disable Windows tips & suggestions",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-338389Enabled",
        desired=0,
        description="Turns off tip cards.",
    ),
    PrivacySetting(
        id="suggested_content",
        label="Disable suggested content in Settings",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-338393Enabled",
        desired=0,
        description="Removes Settings suggestions.",
    ),
    PrivacySetting(
        id="start_suggestions",
        label="Disable Start menu suggestions / OEM apps",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SystemPaneSuggestionsEnabled",
        desired=0,
        description="Stops suggested apps in Start.",
    ),
    PrivacySetting(
        id="silent_app_install",
        label="Disable silent installed apps",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SilentInstalledAppsEnabled",
        desired=0,
        description="Prevents Windows from auto-installing suggested apps.",
    ),
    PrivacySetting(
        id="content_delivery",
        label="Disable Content Delivery Manager",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="ContentDeliveryAllowed",
        desired=0,
        description="Master switch for content delivery pushes.",
    ),
    PrivacySetting(
        id="oem_preinstalled",
        label="Disable OEM preinstalled apps push",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="OemPreInstalledAppsEnabled",
        desired=0,
        description="Stops OEM app re-pushes.",
    ),
    PrivacySetting(
        id="preinstalled_apps",
        label="Disable Microsoft preinstalled apps push",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="PreInstalledAppsEnabled",
        desired=0,
        description="Stops Microsoft preinstalled app re-pushes.",
    ),
    PrivacySetting(
        id="soft_landing",
        label="Disable soft-landing tips",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SoftLandingEnabled",
        desired=0,
        description="Disables first-use tip overlays.",
    ),
    PrivacySetting(
        id="spotlight",
        label="Disable Windows Spotlight lock-screen ads",
        hive="HKCU",
        path=r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        name="DisableWindowsSpotlightFeatures",
        desired=1,
        description="Removes Spotlight consumer content / ads.",
    ),
    PrivacySetting(
        id="consumer_features",
        label="Disable Windows consumer features",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        name="DisableWindowsConsumerFeatures",
        desired=1,
        description="Blocks consumer experience / ads policies.",
    ),
    PrivacySetting(
        id="input_personalization",
        label="Disable inking & typing personalization",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\InputPersonalization",
        name="RestrictImplicitTextCollection",
        desired=1,
        description="Stops harvesting typed text for personalization.",
    ),
    PrivacySetting(
        id="input_contacts",
        label="Disable implicit ink collection",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\InputPersonalization",
        name="RestrictImplicitInkCollection",
        desired=1,
        description="Stops harvesting ink strokes.",
    ),
    PrivacySetting(
        id="online_speech",
        label="Disable online speech recognition",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy",
        name="HasAccepted",
        desired=0,
        description="Keeps speech processing local / off.",
    ),
    PrivacySetting(
        id="location",
        label="Deny apps location access (policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors",
        name="DisableLocation",
        desired=1,
        description="Policy-disables location sensors.",
    ),
    PrivacySetting(
        id="wifi_sense",
        label="Disable Wi-Fi Sense hotspot reporting",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config",
        name="AutoConnectAllowedOEM",
        desired=0,
        description="Stops OEM auto-connect / Sense behaviour.",
    ),
    PrivacySetting(
        id="error_report",
        label="Disable Windows Error Reporting",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting",
        name="Disabled",
        desired=1,
        description="Stops WER from sending crash reports.",
    ),
    PrivacySetting(
        id="app_telemetry",
        label="Disable app launch tracking",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        name="Start_TrackProgs",
        desired=0,
        description="Stops Start from tracking app launches.",
    ),
    PrivacySetting(
        id="clipboard_history",
        label="Disable clipboard history",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\System",
        name="AllowClipboardHistory",
        desired=0,
        description="Turns off clipboard history cloud/local store.",
    ),
    PrivacySetting(
        id="clipboard_sync",
        label="Disable clipboard cloud sync",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\System",
        name="AllowCrossDeviceClipboard",
        desired=0,
        description="Prevents clipboard sync across devices.",
    ),
    # --- Community staples (Win11Debloat / WinUtil / ShutUp10-style) ---
    PrivacySetting(
        id="harvest_contacts",
        label="Disable contacts harvesting for input",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\InputPersonalization\TrainedDataStore",
        name="HarvestContacts",
        desired=0,
        description="WinUtil telemetry tweak: stop harvesting contacts.",
    ),
    PrivacySetting(
        id="personalization_privacy",
        label="Reject personalization privacy policy flag",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Personalization\Settings",
        name="AcceptedPrivacyPolicy",
        desired=0,
        description="Marks inking/typing personalization as not accepted.",
    ),
    PrivacySetting(
        id="telemetry_dual",
        label="AllowTelemetry (CurrentVersion Policies path)",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
        name="AllowTelemetry",
        desired=0,
        description="Second AllowTelemetry path used by WinUtil / many guides.",
    ),
    PrivacySetting(
        id="delivery_optimization",
        label="Delivery Optimization -> HTTP only (no P2P)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization",
        name="DODownloadMode",
        desired=0,
        description="WinUtil: stop uploading updates to other PCs on the internet.",
    ),
    PrivacySetting(
        id="bing_search_enabled",
        label="Disable BingSearchEnabled",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search",
        name="BingSearchEnabled",
        desired=0,
        description="WinUtil / Win11Debloat: local Start search without Bing web.",
    ),
    PrivacySetting(
        id="cortana_consent",
        label="Disable Cortana consent",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Windows Search",
        name="CortanaConsent",
        desired=0,
        description="Turns off Cortana consent / web assist in search.",
    ),
    PrivacySetting(
        id="copilot",
        label="Disable Windows Copilot (policy)",
        hive="HKCU",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
        name="TurnOffWindowsCopilot",
        desired=1,
        description="Win11Debloat: policy-disable Copilot button/integration.",
    ),
    PrivacySetting(
        id="copilot_hklm",
        label="Disable Windows Copilot (machine policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
        name="TurnOffWindowsCopilot",
        desired=1,
        description="Machine-wide Copilot policy (Win11Debloat).",
    ),
    PrivacySetting(
        id="recall_disable",
        label="Disable Windows Recall snapshots",
        hive="HKCU",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="DisableAIDataAnalysis",
        desired=1,
        description="Win11Debloat: block Recall / AI data analysis snapshots.",
    ),
    PrivacySetting(
        id="recall_disable_hklm",
        label="Disable Windows Recall (machine)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="DisableAIDataAnalysis",
        desired=1,
        description="Machine policy for Recall / AI data analysis.",
    ),
    PrivacySetting(
        id="widgets_taskbar",
        label="Hide Widgets on taskbar",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        name="TaskbarDa",
        desired=0,
        description="Win11Debloat: remove Widgets button from taskbar.",
    ),
    PrivacySetting(
        id="news_and_interests",
        label="Disable News and Interests / Widgets feed policy",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Dsh",
        name="AllowNewsAndInterests",
        desired=0,
        description="Policy blocks Widgets / News and Interests feed.",
    ),
    PrivacySetting(
        id="find_my_device",
        label="Disable Find My Device",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\FindMyDevice",
        name="AllowFindMyDevice",
        desired=0,
        description="Win11Debloat privacy: stop Find My Device location reporting.",
    ),
    PrivacySetting(
        id="lock_tips",
        label="Disable lock screen tips / fun facts",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="RotatingLockScreenOverlayEnabled",
        desired=0,
        description="Removes tips/ads overlay on Spotlight lock screen.",
    ),
    PrivacySetting(
        id="subscribed_338388",
        label="Disable Start suggestions (338388)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-338388Enabled",
        desired=0,
        description="Extra Content Delivery suggestion switch (community lists).",
    ),
    PrivacySetting(
        id="subscribed_353694",
        label="Disable Settings suggestions (353694)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-353694Enabled",
        desired=0,
        description="Settings home / account suggestions.",
    ),
    PrivacySetting(
        id="subscribed_353696",
        label="Disable Settings suggestions (353696)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-353696Enabled",
        desired=0,
        description="Additional Settings suggestion content.",
    ),
    PrivacySetting(
        id="edge_hub_sidebar",
        label="Disable Edge Hub sidebar",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="HubsSidebarEnabled",
        desired=0,
        description="Win11Debloat Edge declutter: disable sidebar hub.",
    ),
    PrivacySetting(
        id="edge_startup_boost",
        label="Disable Edge startup boost (policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="StartupBoostEnabled",
        desired=0,
        description="Stops Edge keeping background processes for 'boost'.",
    ),
    PrivacySetting(
        id="game_dvr",
        label="Disable Game DVR / background recording",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
        name="AppCaptureEnabled",
        desired=0,
        description="Win11Debloat: disable Game DVR capture (reduces background load).",
    ),
    # --- Win11Debloat 2026 AI / companion keys ---
    PrivacySetting(
        id="click_to_do",
        label="Disable Click to Do (user policy)",
        hive="HKCU",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="DisableClickToDo",
        desired=1,
        description="Win11Debloat: block Click to Do AI text/image analysis.",
    ),
    PrivacySetting(
        id="click_to_do_hklm",
        label="Disable Click to Do (machine policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="DisableClickToDo",
        desired=1,
        description="Machine-wide Click to Do policy.",
    ),
    PrivacySetting(
        id="recall_allow_enablement",
        label="Block Recall enablement (AllowRecallEnablement=0)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="AllowRecallEnablement",
        desired=0,
        description="Win11Debloat Recall: prevent users from turning Recall on.",
    ),
    PrivacySetting(
        id="recall_turn_off_snapshots",
        label="Turn off Recall snapshot saving",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        name="TurnOffSavingSnapshots",
        desired=1,
        description="Win11Debloat Recall: stop saving snapshots for Recall.",
    ),
    PrivacySetting(
        id="paint_ai_cocreator",
        label="Disable Paint Cocreator AI",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
        name="DisableCocreator",
        desired=1,
        description="Win11Debloat: disable Paint Cocreator.",
    ),
    PrivacySetting(
        id="paint_ai_genfill",
        label="Disable Paint Generative Fill",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
        name="DisableGenerativeFill",
        desired=1,
        description="Win11Debloat: disable Paint Generative Fill.",
    ),
    PrivacySetting(
        id="paint_ai_imagecreator",
        label="Disable Paint Image Creator",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
        name="DisableImageCreator",
        desired=1,
        description="Win11Debloat: disable Paint Image Creator.",
    ),
    PrivacySetting(
        id="paint_ai_generase",
        label="Disable Paint Generative Erase",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
        name="DisableGenerativeErase",
        desired=1,
        description="Win11Debloat: disable Paint Generative Erase.",
    ),
    PrivacySetting(
        id="paint_ai_removebg",
        label="Disable Paint Remove Background AI",
        hive="HKLM",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
        name="DisableRemoveBackground",
        desired=1,
        description="Win11Debloat: disable Paint Remove Background.",
    ),
    PrivacySetting(
        id="notepad_ai",
        label="Disable Notepad AI features",
        hive="HKLM",
        path=r"SOFTWARE\Policies\WindowsNotepad",
        name="DisableAIFeatures",
        desired=1,
        description="Win11Debloat: turn off Notepad AI features.",
    ),
    PrivacySetting(
        id="edge_copilot_page",
        label="Disable Edge Copilot page context",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="CopilotPageContext",
        desired=0,
        description="Win11Debloat Edge AI: Copilot page context off.",
    ),
    PrivacySetting(
        id="edge_copilot_cdp",
        label="Disable Edge Copilot CDP page context",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="CopilotCDPPageContext",
        desired=0,
        description="Win11Debloat Edge AI: Copilot CDP context off.",
    ),
    PrivacySetting(
        id="edge_entra_copilot",
        label="Disable Edge Entra Copilot page context",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="EdgeEntraCopilotPageContext",
        desired=0,
        description="Win11Debloat Edge AI: Entra Copilot context off.",
    ),
    PrivacySetting(
        id="edge_history_ai",
        label="Disable Edge History AI search",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="EdgeHistoryAISearchEnabled",
        desired=0,
        description="Win11Debloat Edge AI: history AI search off.",
    ),
    PrivacySetting(
        id="edge_compose_inline",
        label="Disable Edge Compose inline AI",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="ComposeInlineEnabled",
        desired=0,
        description="Win11Debloat Edge AI: Compose inline off.",
    ),
    PrivacySetting(
        id="edge_genai_local",
        label="Disable Edge local GenAI foundational model",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="GenAILocalFoundationalModelSettings",
        desired=1,
        description="Win11Debloat Edge AI: block local GenAI model download/use.",
    ),
    PrivacySetting(
        id="edge_ntp_bing_chat",
        label="Disable Edge new-tab Bing Chat",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="NewTabPageBingChatEnabled",
        desired=0,
        description="Win11Debloat Edge AI: Bing Chat on NTP off.",
    ),
    PrivacySetting(
        id="edge_personalization",
        label="Disable Edge personalization reporting",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="PersonalizationReportingEnabled",
        desired=0,
        description="Win11Debloat telemetry: Edge personalization reporting off.",
    ),
    PrivacySetting(
        id="edge_diagnostic_data",
        label="Disable Edge diagnostic data",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Edge",
        name="DiagnosticData",
        desired=0,
        description="Win11Debloat telemetry: Edge diagnostic data off.",
    ),
    PrivacySetting(
        id="one_settings_downloads",
        label="Disable OneSettings telemetry config downloads",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        name="DisableOneSettingsDownloads",
        desired=1,
        description="Blocks remote OneSettings telemetry configuration downloads.",
    ),
    PrivacySetting(
        id="max_telemetry_allowed",
        label="MaxTelemetryAllowed -> 0",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        name="MaxTelemetryAllowed",
        desired=0,
        description="Companion cap with AllowTelemetry (edition may still enforce Required).",
    ),
    PrivacySetting(
        id="feedback_notifications_policy",
        label="Do not show feedback notifications (policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        name="DoNotShowFeedbackNotifications",
        desired=1,
        description="Policy-level feedback nag suppression (stickier than SIUF alone).",
    ),
    PrivacySetting(
        id="ceip_enabled",
        label="Disable Customer Experience Improvement Program",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\SQMClient\Windows",
        name="CEIPEnable",
        desired=0,
        description="Policy-disables CEIP (pairs with CEIP scheduled-task disables).",
    ),
    PrivacySetting(
        id="advertising_id_policy",
        label="Disable Advertising ID by Group Policy",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo",
        name="DisabledByGroupPolicy",
        desired=1,
        description="Harder lock than per-user AdvertisingInfo Enabled=0.",
    ),
    PrivacySetting(
        id="game_dvr_enabled",
        label="Disable GameDVR_Enabled",
        hive="HKCU",
        path=r"System\GameConfigStore",
        name="GameDVR_Enabled",
        desired=0,
        description="Win11Debloat DVR companion key in GameConfigStore.",
    ),
    PrivacySetting(
        id="game_dvr_policy",
        label="Disable Game DVR (machine policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\GameDVR",
        name="AllowGameDVR",
        desired=0,
        description="Win11Debloat: AllowGameDVR policy off.",
    ),
    PrivacySetting(
        id="show_copilot_button",
        label="Hide Copilot button on taskbar",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        name="ShowCopilotButton",
        desired=0,
        description="Win11Debloat: hide taskbar Copilot button.",
    ),
    PrivacySetting(
        id="settings_365_ads",
        label="Hide Microsoft 365 ads in Settings Home",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        name="DisableConsumerAccountStateContent",
        desired=1,
        description="Win11Debloat: DisableConsumerAccountStateContent (Settings 365 ads).",
    ),
    PrivacySetting(
        id="tipc",
        label="Disable typing insights (TIPC)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Input\TIPC",
        name="Enabled",
        desired=0,
        description="Win11Debloat telemetry: Improve inking & typing recognition off.",
    ),
    PrivacySetting(
        id="start_iris",
        label="Disable Start Iris recommendations",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        name="Start_IrisRecommendations",
        desired=0,
        description="Win11Debloat suggestions: Start recommendations off.",
    ),
    PrivacySetting(
        id="subscribed_310093",
        label="Disable post-update welcome suggestions (310093)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-310093Enabled",
        desired=0,
        description="Win11Debloat: welcome/suggested content after updates.",
    ),
    PrivacySetting(
        id="subscribed_353698",
        label="Disable Settings suggestions (353698)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        name="SubscribedContent-353698Enabled",
        desired=0,
        description="Additional Settings suggestion content switch.",
    ),
    PrivacySetting(
        id="scoobe",
        label="Disable 'finish setting up your device' (SCOOBE)",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\UserProfileEngagement",
        name="ScoobeSystemSettingEnabled",
        desired=0,
        description="Win11Debloat: stop SCOOBE setup-suggestion nags.",
    ),
    PrivacySetting(
        id="sync_provider_notifications",
        label="Disable sync-provider ads in Explorer",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        name="ShowSyncProviderNotifications",
        desired=0,
        description="Win11Debloat: hide OneDrive/sync provider ads in Explorer.",
    ),
    PrivacySetting(
        id="account_notifications",
        label="Disable account notifications in Settings",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\SystemSettings\AccountNotifications",
        name="EnableAccountNotifications",
        desired=0,
        description="Win11Debloat: Settings account notification nags off.",
    ),
    PrivacySetting(
        id="mobility_optedin",
        label="Disable Phone Link mobility suggestions",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Mobility",
        name="OptedIn",
        desired=0,
        description="Win11Debloat: stop mobile-device pairing suggestions.",
    ),
    PrivacySetting(
        id="search_highlights",
        label="Disable Search Highlights / dynamic search box",
        hive="HKCU",
        path=r"SOFTWARE\Microsoft\Windows\CurrentVersion\SearchSettings",
        name="IsDynamicSearchBoxEnabled",
        desired=0,
        description="Win11Debloat: remove branded/dynamic content in Search.",
    ),
    PrivacySetting(
        id="device_metadata_network",
        label="Prevent device-metadata auto app downloads",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Device Metadata",
        name="PreventDeviceMetadataFromNetwork",
        desired=1,
        description="Win11Debloat: stop auto-download of device-associated apps.",
    ),
    PrivacySetting(
        id="cortana_consent_hklm",
        label="Disable CortanaConsent (machine Search policy)",
        hive="HKLM",
        path=r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
        name="CortanaConsent",
        desired=0,
        description="Win11Debloat Bing/Cortana search: CortanaConsent policy off.",
    ),
]


class PrivacyModule(CleanModule):
    id = "privacy"
    label = "Privacy & Telemetry Hardening"
    description = (
        "Applies registry / policy keys used by popular tools (Win11Debloat, WinUtil, "
        "ShutUp10-style guides): telemetry, ads, Copilot/Recall, Widgets, Delivery "
        "Optimization P2P, Edge hub, Find My Device, and suggestion switches. "
        "Does not uninstall Windows components or touch Defender."
    )
    risk = Risk.MODERATE
    # Many keys are under Policies / HKLM and need elevation on modern Windows.
    requires_admin = True
    default_enabled = True

    def _drift(self) -> list[tuple[PrivacySetting, object]]:
        drifted: list[tuple[PrivacySetting, object]] = []
        for s in SETTINGS:
            current = get_value(s.hive, s.path, s.name)
            if not values_match(current, s.desired):
                drifted.append((s, current))
        return drifted

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for setting, current in self._drift():
            if progress:
                progress(f"Checking {setting.label}")
            path_norm = setting.path.replace("/", "\\")
            needs_admin = setting.hive == "HKLM" or "\\Policies\\" in path_norm
            note = _edition_note(setting.id)
            result.items.append(
                CleanItem(
                    id=setting.id,
                    label=setting.label,
                    detail=(
                        f"{setting.hive}\\{setting.path}\\{setting.name} "
                        f"= {current!r} -> {setting.desired}{note}"
                    ),
                    bytes_estimate=0,
                    requires_admin=needs_admin,
                    effect=setting.description,
                )
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        from windowscleaner.utils.admin import is_admin

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=dry_run)
        admin = is_admin()
        for setting, current in self._drift():
            # On current Windows builds, HKCU\Policies and some Explorer keys also deny non-admin writes.
            needs_admin = setting.hive == "HKLM" or "\\Policies\\" in setting.path.replace("/", "\\")
            if needs_admin and not admin and not dry_run:
                result.items.append(
                    CleanItem(
                        id=setting.id,
                        label=setting.label,
                        detail="Needs Administrator - not applied (will show again on Scan)",
                        bytes_estimate=0,
                        requires_admin=True,
                        effect=setting.description,
                        repercussions="Run Restart as Administrator, then Clean again.",
                    )
                )
                result.errors.append(f"{setting.id}: needs Administrator (write denied without elevation)")
                continue
            if progress:
                progress(f"{'Would set' if dry_run else 'Setting'} {setting.label}")
            change: RegChange = set_dword(
                setting.hive,
                setting.path,
                setting.name,
                setting.desired,
                dry_run=dry_run,
            )
            result.items.append(
                CleanItem(
                    id=setting.id,
                    label=setting.label,
                    detail=setting.description if change.ok else (change.error or "write failed"),
                    bytes_estimate=0,
                    requires_admin=needs_admin,
                    effect=setting.description,
                    repercussions=(
                        "Applied."
                        if change.ok and not dry_run
                        else "Will keep appearing on Scan until write succeeds (usually needs Admin)."
                    ),
                )
            )
            if change.ok:
                result.actions.append(
                    f"{'Would set' if dry_run else 'Set'} {setting.hive}\\{setting.path}\\"
                    f"{setting.name}={setting.desired} (was {current!r})"
                )
            else:
                result.errors.append(
                    f"{setting.id}: {change.error or 'failed to write registry value'}"
                )
        return result
