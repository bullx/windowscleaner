using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Win32;

namespace WindowsCleaner;

public static class PrivacyUndo
{
    private static string PathFile() => Path.Combine(Paths.AppDataDir(), "privacy_undo.json");

    public static void Record(string id, string label, string hive, string path, string name, object? previous, int applied)
    {
        var data = Load();
        var entries = data["entries"] as JsonArray ?? new JsonArray();
        var kept = new JsonArray();
        foreach (var node in entries)
        {
            if (node?["id"]?.GetValue<string>() != id)
                kept.Add(node?.DeepClone());
        }
        kept.Add(new JsonObject
        {
            ["id"] = id,
            ["label"] = label,
            ["hive"] = hive,
            ["path"] = path,
            ["name"] = name,
            ["previous"] = previous is null ? null : JsonValue.Create(Convert.ToInt32(previous)),
            ["applied"] = applied,
            ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
        });
        while (kept.Count > 200)
            kept.RemoveAt(0);
        Save(new JsonObject { ["version"] = 1, ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["entries"] = kept });
    }

    public static (int Ok, int Failed, List<string> Messages) UndoAll(bool dryRun)
    {
        var data = Load();
        var entries = (data["entries"] as JsonArray)?.ToList() ?? [];
        if (entries.Count == 0)
            return (0, 0, ["No privacy undo history found."]);
        var ok = 0;
        var failed = 0;
        var messages = new List<string>();
        var remaining = new JsonArray();
        for (var i = entries.Count - 1; i >= 0; i--)
        {
            var entry = entries[i] as JsonObject;
            if (entry is null)
                continue;
            var label = entry["label"]?.GetValue<string>() ?? entry["id"]?.GetValue<string>() ?? "";
            if (entry["previous"] is null)
            {
                messages.Add($"{label}: no previous value recorded (was missing) — skipped");
                failed++;
                continue;
            }
            int desired;
            try { desired = entry["previous"]!.GetValue<int>(); }
            catch
            {
                messages.Add($"{label}: previous value not a DWORD — skipped");
                failed++;
                remaining.Add(entry.DeepClone());
                continue;
            }
            var hive = entry["hive"]?.GetValue<string>() ?? "";
            var path = entry["path"]?.GetValue<string>() ?? "";
            var name = entry["name"]?.GetValue<string>() ?? "";
            var current = RegistryStore.GetValue(hive, path, name);
            if (RegistryStore.ValuesMatch(current, desired))
            {
                messages.Add($"{label}: already at previous value");
                ok++;
                continue;
            }
            if (dryRun)
            {
                messages.Add($"Would restore {label}: {current} -> {desired}");
                ok++;
                remaining.Add(entry.DeepClone());
                continue;
            }
            var change = RegistryStore.SetDword(hive, path, name, desired, dryRun: false);
            if (change.Ok)
            {
                messages.Add($"Restored {label} to {desired} (was {current})");
                ok++;
            }
            else
            {
                messages.Add($"{label}: {change.Error ?? "restore failed"}");
                failed++;
                remaining.Add(entry.DeepClone());
            }
        }
        if (!dryRun)
        {
            var ordered = new JsonArray();
            for (var i = remaining.Count - 1; i >= 0; i--)
                ordered.Add(remaining[i]?.DeepClone());
            Save(new JsonObject { ["version"] = 1, ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["entries"] = ordered });
        }
        return (ok, failed, messages);
    }

    private static JsonObject Load()
    {
        try
        {
            if (File.Exists(PathFile()))
            {
                var node = JsonNode.Parse(File.ReadAllText(PathFile())) as JsonObject;
                if (node?["entries"] is JsonArray)
                    return node;
            }
        }
        catch { }
        return new JsonObject { ["version"] = 1, ["entries"] = new JsonArray() };
    }

    private static void Save(JsonObject data)
    {
        try { File.WriteAllText(PathFile(), data.ToJsonString(new JsonSerializerOptions { WriteIndented = true })); }
        catch (IOException) { }
    }
}

public static class ChangeUndo
{
    private static string PathFile() => Path.Combine(Paths.AppDataDir(), "change_undo.json");

    public static void RememberRun(string hive, string path, string name, object? value, RegistryValueKind kind)
    {
        Remember(new JsonObject
        {
            ["kind"] = "run",
            ["id"] = $"run:{hive}:{name}",
            ["label"] = $"{hive} Run: {name}",
            ["hive"] = hive,
            ["path"] = path,
            ["name"] = name,
            ["value"] = value?.ToString() ?? "",
            ["reg_type"] = (int)kind,
            ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
        });
    }

    public static void RememberService(string name, string? startText)
    {
        var token = ServiceControl.NormalizeStart(startText);
        if (token is null)
            return;
        Remember(new JsonObject
        {
            ["kind"] = "service",
            ["id"] = $"svc:{name}",
            ["label"] = $"Service start: {name}",
            ["name"] = name,
            ["start"] = token,
            ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
        });
    }

    public static (int Ok, int Failed, List<string> Messages) UndoAll(bool dryRun)
    {
        var data = Load();
        var entries = (data["entries"] as JsonArray)?.ToList() ?? [];
        if (entries.Count == 0)
            return (0, 0, ["No startup or service undo history found."]);
        var ok = 0;
        var failed = 0;
        var messages = new List<string>();
        var remaining = new JsonArray();
        for (var i = entries.Count - 1; i >= 0; i--)
        {
            var entry = entries[i] as JsonObject;
            if (entry is null)
                continue;
            var kind = entry["kind"]?.GetValue<string>();
            var (success, msg, keep) = kind switch
            {
                "run" => RestoreRun(entry, dryRun),
                "service" => RestoreService(entry, dryRun),
                _ => (false, $"{entry["label"]}: unknown undo kind", true),
            };
            messages.Add(msg);
            if (success) ok++; else failed++;
            if (keep) remaining.Add(entry.DeepClone());
        }
        if (!dryRun)
        {
            var ordered = new JsonArray();
            for (var i = remaining.Count - 1; i >= 0; i--)
                ordered.Add(remaining[i]?.DeepClone());
            Save(new JsonObject { ["version"] = 1, ["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), ["entries"] = ordered });
        }
        return (ok, failed, messages);
    }

    private static (bool Ok, string Message, bool Keep) RestoreRun(JsonObject entry, bool dryRun)
    {
        var hive = entry["hive"]?.GetValue<string>() ?? "";
        var path = entry["path"]?.GetValue<string>() ?? "";
        var name = entry["name"]?.GetValue<string>() ?? "";
        var value = entry["value"]?.GetValue<string>();
        var label = entry["label"]?.GetValue<string>() ?? name;
        var kind = (RegistryValueKind)(entry["reg_type"]?.GetValue<int>() ?? (int)RegistryValueKind.String);
        if (hive is not ("HKCU" or "HKLM") || path.Length == 0 || name.Length == 0 || value is null)
            return (false, $"{label}: incomplete record", true);
        if (dryRun)
            return (true, $"Would restore {label}", true);
        try
        {
            RegistryStore.SetValue(hive, path, name, value, kind);
            return (true, $"Restored {label}", false);
        }
        catch (Exception ex)
        {
            return (false, $"{label}: {ex.Message}", true);
        }
    }

    private static (bool Ok, string Message, bool Keep) RestoreService(JsonObject entry, bool dryRun)
    {
        var name = entry["name"]?.GetValue<string>() ?? "";
        var start = ServiceControl.NormalizeStart(entry["start"]?.GetValue<string>());
        var label = entry["label"]?.GetValue<string>() ?? name;
        if (name.Length == 0 || start is null)
            return (false, $"{label}: incomplete record", true);
        if (dryRun)
            return (true, $"Would set {name} start= {start}", true);
        var proc = Proc.Run(["sc", "config", name, "start=", start]);
        return proc.ExitCode == 0
            ? (true, $"Restored {name} start= {start}", false)
            : (false, $"{label}: {proc.Tail}", true);
    }

    private static void Remember(JsonObject entry)
    {
        var data = Load();
        var entries = data["entries"] as JsonArray ?? new JsonArray();
        var id = entry["id"]?.GetValue<string>();
        foreach (var node in entries)
        {
            if (node?["id"]?.GetValue<string>() == id)
                return;
        }
        entries.Add(entry);
        while (entries.Count > 400)
            entries.RemoveAt(0);
        data["entries"] = entries;
        data["when"] = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        data["version"] = 1;
        Save(data);
    }

    private static JsonObject Load()
    {
        try
        {
            if (File.Exists(PathFile()))
            {
                var node = JsonNode.Parse(File.ReadAllText(PathFile())) as JsonObject;
                if (node?["entries"] is JsonArray)
                    return node;
            }
        }
        catch { }
        return new JsonObject { ["version"] = 1, ["entries"] = new JsonArray() };
    }

    private static void Save(JsonObject data)
    {
        try { File.WriteAllText(PathFile(), data.ToJsonString(new JsonSerializerOptions { WriteIndented = true })); }
        catch (IOException) { }
    }
}

public static class WindowsInfo
{
    public static string Edition()
    {
        var value = RegistryStore.GetValue("HKLM", @"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName");
        return value?.ToString() ?? "";
    }

    public static bool IsHome() => Edition().Contains("home", StringComparison.OrdinalIgnoreCase);

    public static string Banner()
    {
        var edition = string.IsNullOrEmpty(Edition()) ? "Windows (edition unknown)" : Edition();
        return IsHome()
            ? $"{edition}: Required diagnostic data may still apply even after privacy policies. Privacy Clean still writes the keys; do not expect fully-off telemetry on Home."
            : $"{edition}: Privacy policies can cap telemetry more tightly than Home. Security/required data may still apply by Microsoft policy.";
    }

    public static string TelemetryNote(string settingId)
    {
        if (settingId is not ("telemetry_level" or "telemetry_dual" or "max_telemetry_allowed") || !IsHome())
            return "";
        return " Note: on Windows Home, Microsoft may still enforce Required diagnostic data even when this policy is 0 — Scan/Clean still apply the key.";
    }
}

public static class ItemText
{
    public static void Enrich(ModuleResult result)
    {
        foreach (var item in result.Items)
        {
            if (!string.IsNullOrEmpty(item.Effect) && !string.IsNullOrEmpty(item.Repercussions))
                continue;
            var lookupId = item.Id.StartsWith("svc:", StringComparison.Ordinal) || item.Id.StartsWith("task:", StringComparison.Ordinal)
                ? item.Id.Split(':', 2)[^1]
                : item.Id;
            var (effect, reper) = Describe(result.ModuleId, lookupId, item.Effect, item.Repercussions);
            if (result.ModuleId == "startup_services" && (item.Id.StartsWith("svc:") || item.Id.StartsWith("usvc:")))
            {
                effect = string.IsNullOrEmpty(item.Effect) ? $"Changes optional startup service: {item.Label.Replace("Service: ", "")}." : item.Effect;
                reper = string.IsNullOrEmpty(item.Repercussions)
                    ? "Frees the RAM it used at boot. Re-enable in services.msc. Uncheck the row if you still use that feature."
                    : item.Repercussions;
            }
            else if (item.Id.StartsWith("svc:", StringComparison.Ordinal))
            {
                effect = $"Disables the '{item.Label.Replace("Service: ", "")}' Windows service (startup = Disabled).";
                reper = "Service stops auto-starting. Re-enable in services.msc. Does not delete Windows files.";
            }
            else if (item.Id.StartsWith("task:", StringComparison.Ordinal))
            {
                effect = $"Disables scheduled task: {item.Label.Replace("Task: ", "")}.";
                reper = "Task will not run on schedule. Re-enable in Task Scheduler. Does not delete the task.";
            }
            else if (result.ModuleId == "bloatware")
            {
                if (item.Id.StartsWith("provisioned:"))
                {
                    effect = $"Deprovisions app package: {item.Label}.";
                    reper = "Stops returning for new users. Reinstall from Store if needed.";
                }
                else
                {
                    effect = $"Uninstalls app package: {item.Label}.";
                    reper = "Removed until reinstalled from Microsoft Store. App data for it is lost.";
                }
            }
            else if (result.ModuleId == "bloatware_oem")
            {
                if (item.Id.StartsWith("winget:"))
                {
                    effect = $"Uninstalls Win32/OEM app via winget: {item.Label}.";
                    reper = "Aggressive. Leftovers/services may remain; OEM may reinstall.";
                }
                else
                {
                    effect = $"Uninstalls OEM AppX: {item.Label}.";
                    reper = "OEM Store package removed; may return via drivers/BIOS.";
                }
            }
            else if (result.ModuleId == "perf_services" && item.Id.StartsWith("svc:"))
            {
                effect = $"Disables optional performance service: {item.Label.Replace("Service: ", "")}.";
                reper = "Can help or hurt. Re-enable in services.msc.";
            }
            if (string.IsNullOrEmpty(item.Effect))
                item.Effect = effect;
            if (string.IsNullOrEmpty(item.Repercussions))
                item.Repercussions = reper;
        }
    }

    public static (string Effect, string Repercussions) Describe(string moduleId, string itemId, string fallbackEffect, string fallbackReper)
    {
        if (moduleId == "privacy")
        {
            var effect = string.IsNullOrEmpty(fallbackEffect) ? Pair("privacy", "_default").Effect : fallbackEffect;
            var reper = Catalogs.PrivacyRepercussions.GetValueOrDefault(itemId) ?? Pair("privacy", "_default").Repercussions;
            if (!string.IsNullOrEmpty(fallbackReper))
                reper = fallbackReper;
            return (effect, reper);
        }
        if (Catalogs.ItemInfo.TryGetValue(moduleId, out var table))
        {
            if (table.TryGetValue(itemId, out var exact))
                return exact;
            if (table.TryGetValue("_default", out var def))
                return (string.IsNullOrEmpty(fallbackEffect) ? def.Effect : fallbackEffect, string.IsNullOrEmpty(fallbackReper) ? def.Repercussions : fallbackReper);
        }
        return (
            string.IsNullOrEmpty(fallbackEffect) ? "Performs this cleanup action." : fallbackEffect,
            string.IsNullOrEmpty(fallbackReper) ? "See module description for risk level." : fallbackReper);
    }

    private static (string Effect, string Repercussions) Pair(string module, string id) =>
        Catalogs.ItemInfo[module][id];
}

public static class Reports
{
    public static string ToText(CleanReport report, string mode)
    {
        var lines = new List<string>
        {
            $"{AppInfo.Name} v{AppInfo.Version} — {mode} report",
            $"When: {DateTime.Now:yyyy-MM-ddTHH:mm:ss}",
            $"Edition: {(string.IsNullOrEmpty(WindowsInfo.Edition()) ? "unknown" : WindowsInfo.Edition())}",
            $"Administrator: {(report.Admin ? "yes" : "no")}",
            $"Dry-run: {(report.DryRun ? "yes" : "no")}",
            $"Estimate: {Sizes.Format(report.BytesEstimate)} · Freed: {Sizes.Format(report.BytesFreed)}",
        };
        if (report.VerifyCounts.Count > 0)
            lines.Add("Verify: " + string.Join(", ", report.VerifyCounts.OrderBy(p => p.Key).Select(p => $"{p.Key}={p.Value}")));
        if (report.SkippedModules.Count > 0)
            lines.Add("Admin-blocked modules: " + string.Join("; ", report.SkippedModules));
        lines.Add("");
        foreach (var mod in report.Results)
        {
            if (mod.Items.Count == 0 && mod.Actions.Count == 0 && mod.Errors.Count == 0)
                continue;
            lines.Add($"## {mod.Label} ({mod.ModuleId})");
            foreach (var item in mod.Items)
            {
                lines.Add($"  [{(string.IsNullOrEmpty(item.Status) ? "-" : item.Status)}] {item.Label} ({Sizes.Format(item.BytesEstimate)}) — {item.Detail}");
                if (!string.IsNullOrEmpty(item.NextStep))
                    lines.Add($"    What to do: {item.NextStep}");
            }
            foreach (var action in mod.Actions)
                lines.Add($"  action: {action}");
            foreach (var error in mod.Errors)
                lines.Add($"  error: {error}");
            lines.Add("");
        }
        return string.Join(Environment.NewLine, lines).TrimEnd() + Environment.NewLine;
    }

    public static string Save(CleanReport report, string mode, string? path, bool asJson)
    {
        path ??= Path.Combine(Paths.AppDataDir(), $"report-{mode}-{DateTime.Now:yyyyMMdd-HHmmss}.{(asJson ? "json" : "txt")}");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var json = path.EndsWith(".json", StringComparison.OrdinalIgnoreCase) || asJson;
        var body = json ? ToJson(report, mode) : ToText(report, mode);
        File.WriteAllText(path, body);
        var last = Path.Combine(Paths.AppDataDir(), json ? "last_report.json" : "last_report.txt");
        try { File.WriteAllText(last, body); } catch (IOException) { }
        return path;
    }

    public static string ToJson(CleanReport report, string mode)
    {
        var root = new JsonObject
        {
            ["app"] = AppInfo.Name,
            ["version"] = AppInfo.Version,
            ["mode"] = mode,
            ["when"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            ["admin"] = report.Admin,
            ["dry_run"] = report.DryRun,
            ["edition"] = WindowsInfo.Edition(),
            ["bytes_estimate"] = report.BytesEstimate,
            ["bytes_freed"] = report.BytesFreed,
            ["verify_counts"] = new JsonObject(),
            ["skipped_modules"] = new JsonArray(report.SkippedModules.Select(s => JsonValue.Create(s)).ToArray()),
            ["modules"] = new JsonArray(),
        };
        foreach (var pair in report.VerifyCounts)
            root["verify_counts"]![pair.Key] = pair.Value;
        foreach (var mod in report.Results)
        {
            var items = new JsonArray();
            foreach (var item in mod.Items)
            {
                items.Add(new JsonObject
                {
                    ["id"] = item.Id,
                    ["label"] = item.Label,
                    ["status"] = item.Status,
                    ["next_step"] = item.NextStep,
                    ["detail"] = item.Detail,
                    ["effect"] = item.Effect,
                    ["repercussions"] = item.Repercussions,
                    ["bytes_estimate"] = item.BytesEstimate,
                    ["requires_admin"] = item.RequiresAdmin,
                    ["risk"] = item.Risk,
                });
            }
            root["modules"]!.AsArray().Add(new JsonObject
            {
                ["id"] = mod.ModuleId,
                ["label"] = mod.Label,
                ["bytes_estimate"] = mod.BytesEstimate,
                ["bytes_freed"] = mod.BytesFreed,
                ["actions"] = new JsonArray(mod.Actions.Select(a => JsonValue.Create(a)).ToArray()),
                ["errors"] = new JsonArray(mod.Errors.Select(a => JsonValue.Create(a)).ToArray()),
                ["items"] = items,
            });
        }
        return root.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
    }
}

public static class Maintenance
{
    public const string WeeklyTask = "WindowsCleaner-FreeDisk";

    public static (bool Ok, string Message) CreateRestorePoint(string description = "Windows Cleaner checkpoint")
    {
        var safe = description.Replace("'", "").Replace("\"", "");
        var script = $"$ErrorActionPreference = 'Stop'; Checkpoint-Computer -Description '{safe}' -RestorePointType MODIFY_SETTINGS; 'OK'";
        var proc = Proc.PowerShell(script, 180_000);
        var combined = (proc.Stdout + "\n" + proc.Stderr).Trim();
        if (proc.ExitCode == 0 && proc.Stdout.Contains("OK", StringComparison.OrdinalIgnoreCase))
            return (true, "System Restore point created.");
        if (combined.Contains("0x80070422") || combined.Contains("disabled", StringComparison.OrdinalIgnoreCase))
            return (false, "System Restore appears disabled.");
        if (combined.Contains("2147942487") || combined.Contains("already been created", StringComparison.OrdinalIgnoreCase) || combined.Contains("0x8004230f", StringComparison.OrdinalIgnoreCase))
            return (false, "A restore point was recently created (Windows rate-limit).");
        var last = combined.Split('\n', StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        return (false, string.IsNullOrEmpty(last) ? $"Restore point failed (exit {proc.ExitCode})." : last);
    }

    public static (bool Ok, string Message) ScheduleWeeklyDisk()
    {
        var exe = Environment.ProcessPath ?? "";
        var command = $"\"{exe}\" --cli clean --profile disk -y";
        var proc = Proc.Run(["schtasks", "/Create", "/F", "/TN", WeeklyTask, "/SC", "WEEKLY", "/D", "SUN", "/ST", "09:00", "/RL", "LIMITED", "/TR", command], 60_000);
        return proc.ExitCode == 0
            ? (true, $"Scheduled {WeeklyTask} every Sunday at 09:00. It runs a Free disk clean.")
            : (false, proc.Tail.Length > 500 ? proc.Tail[..500] : proc.Tail);
    }
}

public static class Disclaimer
{
    public const string Short =
        "Use at your own risk. Scan and Dry-run first. Create a restore point before Clean. " +
        "Bloatware/OEM removal and some privacy tweaks are hard to undo. Not affiliated with Microsoft.";

    public const string Full =
        """
        DISCLAIMER — read before using Windows Cleaner

        This software is provided "as is", without warranty of any kind, express or implied.
        You use it at your own risk. The authors and distributors are not liable for data loss,
        broken apps, lost OEM utilities, failed rollbacks, or any other damage.

        What this tool can do
          • Delete temporary files, caches, logs, Recycle Bin contents, and (if present) Windows.old
          • Optionally delete local AI caches, chats, or downloaded model weights (weights start unchecked)
          • Optionally compact a WSL virtual disk or prune Docker build cache (the distro stays)
          • Optionally clean the component store, hibernation file, or old unused drivers
          • Change privacy / AI / telemetry registry and policy settings
          • Disable services and scheduled tasks
          • Uninstall Store (AppX) apps and deprovision them for new users
          • Optionally uninstall OEM / Win32 software via winget
          • Optionally disable SysMain or Windows Search (can help or hurt performance)
          • Optionally stop unused startup services (Fax, Xbox, print spooler, and similar).
            Never Windows Defender, Windows Update, audio, Wi-Fi, or Windows Hello

        Important limits
          • Not every "slow PC" cause is covered. Telemetry and bloat help some systems; others
            need driver fixes, free disk space, or fewer startup apps.
          • Windows Home may still send Required diagnostic data even when telemetry policies are set.
          • OEM tools (SupportAssist, HP Wolf, Lenovo Vantage, AV trials) may reinstall via
            drivers, BIOS, or Windows Update. McAfee/Norton often need the vendor removal tool.
          • App uninstalls are irreversible without reinstalling from the Microsoft Store (or OEM).
          • Deleting Windows.old permanently removes the previous Windows install / rollback.
          • Disabling WSearch hurts Start/file search; disabling SysMain can slow cold launches on SSDs.

        Safety habits
          1. Prefer Scan → Dry-run → Clean
          2. Enable "Create System Restore point" before Clean (when available)
          3. Run as Administrator only when you need privacy / services / system / bloat changes
          4. Review Aggressive modules item-by-item before Clean
          5. This tool does NOT disable Windows Defender or Windows Update, and does not touch
             BitLocker, disk partitions, or WinRE

        Affiliation
          Not affiliated with, endorsed by, or sponsored by Microsoft Corporation or any PC OEM.
          Methods use documented Windows APIs, folders, registry policies, services, Task Scheduler,
          PowerShell AppX, and winget. No exploits.

        By clicking Clean (or confirming in the CLI) you acknowledge that you understand these risks
        and accept full responsibility for changes made to your system.
        """;

    public const string How =
        """
        How this works

        Windows Cleaner only runs while you Scan, Dry-run, or Clean. It is not a background optimizer.

        Scan lists files, registry values, services, tasks, and Store packages that are already on this PC.
        Dry-run shows the same rows and does not change them.
        Clean applies the checked rows, then scans again. Status becomes Fixed, Not fixed, Still present,
        or Failed — Needs Admin from that second look. A later Scan can say Came back when a cache refills,
        which is normal.

        The actions are ordinary Windows mechanisms: deleting cache folders, emptying the Recycle Bin,
        writing documented policy values, sc config / schtasks, Remove-AppxPackage, winget uninstall,
        DISM component cleanup, and pnputil for driver packages no connected device is using.

        It does not disable Windows Defender or Windows Update, and it does not search the disk for
        folders with "AI" in the name. AI cleanup uses a fixed list of known tool paths.
        """;
}
