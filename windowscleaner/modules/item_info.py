"""Human-readable effect / repercussion text for scanned items."""

from __future__ import annotations

from windowscleaner.modules.base import ModuleResult

# module_id -> item_id -> (effect, repercussions)
ITEM_INFO: dict[str, dict[str, tuple[str, str]]] = {
    "temp_files": {
        "_default": (
            "Deletes temporary files Windows and apps left behind.",
            "Almost none. In-use files are skipped. Some apps recreate temps immediately.",
        ),
        "windows_temp": (
            "Clears C:\\Windows\\Temp system temporary files.",
            "Needs Admin. Locked files remain until reboot. Safe for normal use.",
        ),
        "recent": (
            "Clears Jump List / Recent documents shortcuts.",
            "Recent files lists in Explorer and Jump Lists reset (files themselves stay).",
        ),
        "minidump_user": (
            "Deletes user-mode crash dump files.",
            "You lose those crash dumps for debugging. Frees a lot of space if dumps piled up.",
        ),
        "wer_user": (
            "Clears Windows Error Reporting user archives.",
            "Past crash reports for Feedback/WER are removed. Does not affect running apps.",
        ),
        "iedownload": (
            "Clears Internet / WinINet cache leftovers.",
            "Some sites may reload cached content next visit. No bookmarks/passwords touched.",
        ),
    },
    "recycle_bin": {
        "_default": (
            "Permanently empties the Recycle Bin on all drives.",
            "Deleted files cannot be restored from the Bin afterward. Irreversible.",
        ),
    },
    "browser_caches": {
        "_default": (
            "Deletes browser cache files (images, scripts, etc.).",
            "Sites may load slower once. Bookmarks, passwords, and extensions are kept. Close the browser first.",
        ),
    },
    "gpu_caches": {
        "_default": (
            "Deletes GPU / DirectX shader caches.",
            "Games/apps may hitch briefly while shaders recompile. No settings or saves are touched.",
        ),
    },
    "caches": {
        "_default": (
            "Clears a Windows system/update cache folder.",
            "Usually safe. Some caches rebuild automatically.",
        ),
        "wu_download": (
            "Deletes downloaded Windows Update packages waiting to install / leftovers.",
            "Needs Admin. Next update may re-download. Do not clean mid-update.",
        ),
        "delivery_opt": (
            "Clears Delivery Optimization P2P cache.",
            "Stops using/serving update bits to other PCs until it refills. Updates still work.",
        ),
        "delivery_opt_alt": (
            "Clears Delivery Optimization service cache files.",
            "Same as DO cache - safe; may re-download peer bits later.",
        ),
        "do_programdata": (
            "Clears Delivery Optimization ProgramData leftovers.",
            "Safe space reclaim; DO may recreate folders.",
        ),
        "thumbcache": (
            "Deletes Explorer thumbnail / icon cache databases.",
            "Folders briefly show generic icons until thumbnails rebuild.",
        ),
        "font_cache": (
            "Clears font cache service files.",
            "Fonts may redraw oddly until cache rebuilds; rare visual glitch until reboot.",
        ),
        "prefetch": (
            "Deletes Prefetch (.pf) hints Windows uses to speed app launches.",
            "Next few cold boots/app starts can be slightly slower, then Prefetch rebuilds.",
        ),
        "installer_cache_partial": (
            "Clears Windows Installer patch cache leftovers.",
            "Rarely, repair/uninstall of an old MSI may need the original media again.",
        ),
        "webcache": (
            "Clears Windows WebCache (Explorer/legacy web leftovers).",
            "Some Explorer web-related history/cache is wiped. Usually safe.",
        ),
        "windows_old": (
            "Deletes C:\\Windows.old left after a feature update / in-place upgrade.",
            "IRREVERSIBLE. You cannot roll back to the previous Windows install afterward. "
            "Often frees 10–30+ GB. Needs Admin; some files may need reboot if locked.",
        ),
    },
    "logs": {
        "_default": (
            "Deletes diagnostic / setup / crash log files.",
            "You lose those logs for troubleshooting. OS keeps working normally.",
        ),
        "memory_dmp": (
            "Deletes the full MEMORY.DMP kernel crash dump.",
            "Cannot analyze that blue-screen dump afterward. Often hundreds of MB–GB freed.",
        ),
        "minidump": (
            "Deletes kernel minidump files.",
            "Past BSOD minidumps are gone. Useful space save if you don't debug crashes.",
        ),
        "diagtrack_etl": (
            "Clears Diagnosis / telemetry staging files.",
            "Telemetry staging data is wiped; service may recreate empty folders.",
        ),
    },
    "tracking": {
        "_default": (
            "Removes local tracking / activity / suggestion data.",
            "Timeline, suggestions, or histories reset. Apps themselves stay installed.",
        ),
        "activity_history": (
            "Clears Timeline / Connected Devices activity databases.",
            "Activity History / Timeline entries disappear (local). Cloud copy may remain if sync was on.",
        ),
        "notifications": (
            "Clears Notification Center history.",
            "Old notifications are gone. New ones still appear.",
        ),
        "clipboard": (
            "Clears clipboard history cache.",
            "Pinned/history clipboard entries are lost. Current paste buffer may reset.",
        ),
        "cdm": (
            "Clears Content Delivery Manager suggestion caches.",
            "Start/lock suggestion content refreshes from Microsoft later unless privacy keys block it.",
        ),
        "search_cortana": (
            "Clears Search / Cortana local caches and DBs.",
            "Local search history/suggestions reset. Search still works.",
        ),
        "cortana_pkg": (
            "Clears Cortana package local data.",
            "Cortana leftovers wiped; feature may be already unused on Win11.",
        ),
        "onedrive_logs": (
            "Deletes OneDrive sync log files.",
            "Harder to diagnose OneDrive sync issues until new logs appear. Files in cloud stay.",
        ),
        "speech": (
            "Clears speech services cache.",
            "Voice typing may re-download small models. Dictation still available if enabled.",
        ),
        "diag_programdata": (
            "Clears shared diagnostics staging under ProgramData.",
            "Needs Admin often. Telemetry staging wiped; folders may recreate.",
        ),
    },
    "network_cache": {
        "_default": (
            "Flushes the DNS resolver cache.",
            "None lasting. DNS lookups refill as you browse. Can fix stale DNS briefly.",
        ),
    },
    "privacy": {
        "_default": (
            "Writes a privacy / policy registry value to reduce tracking or ads.",
            "Some Windows 'helpful' features (suggestions, cloud clipboard, web search) stop. Reversible via Settings/regedit.",
        ),
    },
    "telemetry_services": {
        "_default": (
            "Disables a telemetry-related service or scheduled task.",
            "That background uploader/task stops. Reversible in services.msc / Task Scheduler. Does not delete Windows.",
        ),
    },
    "bloatware": {
        "_default": (
            "Uninstalls this preinstalled Store / OEM app for your user (and tries all users).",
            "App is removed until you reinstall from Microsoft Store. Settings/data for that app are lost.",
        ),
    },
    "bloatware_oem": {
        "_default": (
            "Removes OEM / Win32 / winget-listed junk when Clean runs elevated.",
            "Aggressive. Some OEM tools reinstall via BIOS/drivers. Review each item before Clean.",
        ),
    },
    "perf_services": {
        "_default": (
            "Disables an optional performance-related Windows service.",
            "Can help or hurt depending on disk/RAM. Re-enable in services.msc. Not in Standard profile.",
        ),
    },
}

# Privacy setting id -> repercussions (effect uses PrivacySetting.description)
PRIVACY_REPERCUSSIONS: dict[str, str] = {
    "telemetry_level": "Some optional diagnostics stop. Security/required data may still apply by edition. Windows Update unaffected.",
    "advertising_id": "Apps can no longer use your advertising ID for personalized ads.",
    "activity_history_publish": "Timeline may be empty / not publish activities.",
    "activity_history_upload": "Activity History will not upload to your Microsoft account.",
    "activity_feed": "Activity feed features turn off.",
    "cortana": "Cortana stays disabled by policy.",
    "web_search": "Start search stays local (no web results).",
    "bing_search": "Bing suggestions hidden from search box.",
    "bing_search_enabled": "Bing web search in Start is off.",
    "tips": "Tip cards / suggestions reduce or stop.",
    "start_suggestions": "Suggested apps in Start stop appearing.",
    "silent_app_install": "Windows stops auto-installing suggested Store apps.",
    "content_delivery": "Many suggestion/content pushes stop.",
    "spotlight": "Spotlight lock-screen consumer content/ads stop.",
    "consumer_features": "Consumer experience / suggested apps policies apply.",
    "input_personalization": "Typing personalization data is not collected.",
    "online_speech": "Online speech recognition stays off.",
    "location": "Location-using apps may fail until you re-enable location.",
    "error_report": "Crash reports are not sent via WER.",
    "clipboard_history": "Win+V clipboard history unavailable.",
    "clipboard_sync": "Clipboard will not sync across devices.",
    "delivery_optimization": "No P2P upload of updates to other PCs on the internet.",
    "copilot": "Copilot button/integration disabled by policy.",
    "copilot_hklm": "Machine-wide Copilot policy off.",
    "recall_disable": "Windows Recall snapshots blocked.",
    "recall_disable_hklm": "Machine-wide Recall / AI analysis blocked.",
    "widgets_taskbar": "Widgets icon hidden from taskbar.",
    "news_and_interests": "Widgets / News feed policy-blocked.",
    "find_my_device": "Find My Device will not locate this PC.",
    "edge_hub_sidebar": "Edge sidebar hub disabled by policy.",
    "edge_startup_boost": "Edge won't keep boost processes; cold start may be slightly slower.",
    "game_dvr": "Game Bar background recording / DVR capture off.",
    "click_to_do": "Click to Do AI analysis unavailable for this user.",
    "click_to_do_hklm": "Click to Do blocked machine-wide.",
    "recall_allow_enablement": "Users cannot turn Recall on via Settings.",
    "recall_turn_off_snapshots": "Recall will not save snapshots.",
    "paint_ai_cocreator": "Paint Cocreator AI unavailable.",
    "paint_ai_genfill": "Paint Generative Fill unavailable.",
    "paint_ai_imagecreator": "Paint Image Creator unavailable.",
    "paint_ai_generase": "Paint Generative Erase unavailable.",
    "paint_ai_removebg": "Paint Remove Background AI unavailable.",
    "notepad_ai": "Notepad AI features unavailable.",
    "edge_copilot_page": "Edge Copilot page context off.",
    "edge_copilot_cdp": "Edge Copilot CDP context off.",
    "edge_entra_copilot": "Edge Entra Copilot context off.",
    "edge_history_ai": "Edge History AI search off.",
    "edge_compose_inline": "Edge Compose inline AI off.",
    "edge_genai_local": "Edge local GenAI model blocked.",
    "edge_ntp_bing_chat": "Bing Chat on Edge new tab off.",
    "edge_personalization": "Edge stops sending personalization browsing signals.",
    "edge_diagnostic_data": "Edge optional diagnostic data off.",
    "one_settings_downloads": "Remote OneSettings telemetry config pulls blocked.",
    "max_telemetry_allowed": "Telemetry ceiling lowered; Home may still require baseline data.",
    "feedback_notifications_policy": "Feedback notification prompts suppressed by policy.",
    "ceip_enabled": "Customer Experience Improvement Program off by policy.",
    "advertising_id_policy": "Advertising ID disabled by policy for all users.",
    "game_dvr_enabled": "Game DVR flag off in GameConfigStore.",
    "game_dvr_policy": "Game DVR disallowed by machine policy.",
    "show_copilot_button": "Copilot button hidden from taskbar.",
    "settings_365_ads": "Microsoft 365 ads on Settings Home suppressed.",
    "tipc": "Typing insights (TIPC) collection off.",
    "start_iris": "Start Iris recommendations stop.",
    "subscribed_310093": "Post-update welcome suggestions stop.",
    "subscribed_353698": "Additional Settings suggestion content off.",
    "scoobe": "'Finish setting up your device' nags stop.",
    "sync_provider_notifications": "Sync-provider ads in Explorer stop.",
    "account_notifications": "Settings account notification nags stop.",
    "mobility_optedin": "Phone Link mobility suggestions stop.",
    "search_highlights": "Dynamic/branded Search Highlights off.",
    "device_metadata_network": "Windows won't auto-download device metadata apps from the network.",
    "cortana_consent_hklm": "Cortana consent blocked in Search policy.",
}


def describe_item(
    module_id: str,
    item_id: str,
    *,
    fallback_effect: str = "",
    fallback_repercussions: str = "",
) -> tuple[str, str]:
    if module_id == "privacy":
        effect = fallback_effect or ITEM_INFO["privacy"]["_default"][0]
        reper = PRIVACY_REPERCUSSIONS.get(item_id) or ITEM_INFO["privacy"]["_default"][1]
        if fallback_repercussions:
            reper = fallback_repercussions
        return effect, reper

    table = ITEM_INFO.get(module_id, {})
    if item_id in table:
        return table[item_id]
    if "_default" in table:
        effect, reper = table["_default"]
        return fallback_effect or effect, fallback_repercussions or reper
    return (
        fallback_effect or "Performs this cleanup action.",
        fallback_repercussions or "See module description for risk level.",
    )


def enrich_result(result: ModuleResult) -> ModuleResult:
    """Ensure every item has effect + repercussions text for the UI."""
    for item in result.items:
        if item.effect and item.repercussions:
            continue
        # Privacy items often already carry a description in detail
        fallback_effect = item.effect
        if result.module_id == "privacy" and not fallback_effect:
            fallback_effect = item.detail if item.detail and "->" not in item.detail else (
                ITEM_INFO["privacy"]["_default"][0]
            )
            if item.detail and not item.detail.startswith("HK") and "->" not in item.detail:
                fallback_effect = item.detail
        eff, rep = describe_item(
            result.module_id,
            item.id.split(":")[-1] if item.id.startswith(("svc:", "task:")) else item.id,
            fallback_effect=fallback_effect,
            fallback_repercussions=item.repercussions,
        )
        # Services/tasks keep specific default text
        if item.id.startswith("svc:"):
            eff = f"Disables the '{item.label.replace('Service: ', '')}' Windows service (startup = Disabled)."
            rep = "Service stops auto-starting. Re-enable in services.msc. Does not delete Windows files."
        elif item.id.startswith("task:"):
            eff = f"Disables scheduled task: {item.label.replace('Task: ', '')}."
            rep = "Task will not run on schedule. Re-enable in Task Scheduler. Does not delete the task."
        elif result.module_id == "bloatware":
            if item.id.startswith("provisioned:"):
                eff = f"Deprovisions app package: {item.label}."
                rep = "Stops returning for new users. Reinstall from Store if needed."
            else:
                eff = f"Uninstalls app package: {item.label}."
                rep = "Removed until reinstalled from Microsoft Store. App data for it is lost."
        elif result.module_id == "bloatware_oem":
            if item.id.startswith("winget:"):
                eff = f"Uninstalls Win32/OEM app via winget: {item.label}."
                rep = "Aggressive. Leftovers/services may remain; OEM may reinstall."
            else:
                eff = f"Uninstalls OEM AppX: {item.label}."
                rep = "OEM Store package removed; may return via drivers/BIOS."
        elif result.module_id == "perf_services" and item.id.startswith("svc:"):
            eff = f"Disables optional performance service: {item.label.replace('Service: ', '')}."
            rep = "Can help or hurt. Re-enable in services.msc."
        item.effect = item.effect or eff
        item.repercussions = item.repercussions or rep
    return result
