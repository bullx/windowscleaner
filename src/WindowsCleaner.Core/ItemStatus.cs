using System.Text.Json.Nodes;

namespace WindowsCleaner;

public static class ItemStatus
{
    public static readonly Dictionary<string, string> ModuleKind = new()
    {
        ["temp_files"] = "ephemeral",
        ["recycle_bin"] = "ephemeral",
        ["browser_caches"] = "ephemeral",
        ["browser_privacy"] = "ephemeral",
        ["gpu_caches"] = "ephemeral",
        ["caches"] = "ephemeral",
        ["app_caches"] = "ephemeral",
        ["dev_caches"] = "ephemeral",
        ["logs"] = "ephemeral",
        ["tracking"] = "ephemeral",
        ["network_cache"] = "maintenance",
        ["privacy"] = "sticky",
        ["telemetry_services"] = "sticky",
        ["bloatware"] = "sticky",
        ["bloatware_oem"] = "sticky",
        ["perf_services"] = "sticky",
        ["startup_apps"] = "sticky",
        ["startup_services"] = "sticky",
        ["ai_caches"] = "ephemeral",
        ["ai_history"] = "ephemeral",
        ["ai_models"] = "sticky",
        ["dev_disks"] = "ephemeral",
        ["system_reclaim"] = "sticky",
        ["driver_store"] = "sticky",
        ["windows_features"] = "sticky",
    };

    public static readonly HashSet<string> AdminModules =
    [
        "privacy", "telemetry_services", "bloatware", "bloatware_oem", "perf_services",
        "startup_services", "system_reclaim", "driver_store", "windows_features",
    ];

    private static readonly HashSet<string> FailStatuses = ["Failed", "Failed — Needs Admin", "Needs Admin", "Dry-run"];

    public static string HistoryPath() => Path.Combine(Paths.AppDataDir(), "last_clean.json");

    public static string Key(string moduleId, string itemId) => $"{moduleId}::{itemId}";

    public static JsonObject LoadHistory()
    {
        try
        {
            var path = HistoryPath();
            if (File.Exists(path))
            {
                var node = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
                if (node?["items"] is JsonObject)
                    return node;
            }
        }
        catch (Exception ex) when (ex is IOException or System.Text.Json.JsonException)
        {
        }
        return new JsonObject { ["version"] = 1, ["when"] = 0, ["admin"] = false, ["items"] = new JsonObject(), ["skipped_modules"] = new JsonArray() };
    }

    public static void SaveHistory(JsonObject data)
    {
        try { File.WriteAllText(HistoryPath(), data.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true })); }
        catch (IOException) { }
    }

    public static void AnnotateScan(ModuleResult result, JsonObject? history = null)
    {
        history ??= LoadHistory();
        var items = history["items"] as JsonObject ?? new JsonObject();
        var admin = Admin.IsAdmin();
        var kind = ModuleKind.GetValueOrDefault(result.ModuleId, "ephemeral");
        var skipped = new HashSet<string>();
        if (history["skipped_modules"] is JsonArray arr)
        {
            foreach (var node in arr)
            {
                var text = node?.GetValue<string>();
                if (!string.IsNullOrEmpty(text))
                    skipped.Add(text);
            }
        }
        var moduleSkipped = skipped.Contains(result.ModuleId) || items[Key(result.ModuleId, "__module_skipped__")] is not null;
        foreach (var item in result.Items)
        {
            AnnotateScanItem(result.ModuleId, item, kind, items[Key(result.ModuleId, item.Id)] as JsonObject, admin, moduleSkipped);
        }
    }

    public static void AnnotateClean(ModuleResult result, bool dryRun, bool admin)
    {
        var kind = ModuleKind.GetValueOrDefault(result.ModuleId, "ephemeral");
        foreach (var item in result.Items)
        {
            var detail = (item.Detail ?? "").ToLowerInvariant();
            var reper = (item.Repercussions ?? "").ToLowerInvariant();
            var itemErrors = ErrorsFor(item, result.Errors);
            var adminFail = LooksAdmin(item.Detail) || itemErrors.Any(LooksAdmin);
            var blocked = item.RequiresAdmin && !admin && !dryRun;
            var failed = blocked || detail.Contains("needs administrator") || detail.Contains("write failed")
                || reper.Contains("will keep appearing") || detail.Contains("skipped (needs administrator)") || itemErrors.Count > 0;
            var needsAdmin = blocked || adminFail || detail.Contains("needs administrator");
            if (dryRun)
            {
                item.Status = "Dry-run";
                item.NextStep = "Run Clean to apply";
                continue;
            }
            if (failed)
            {
                item.Status = needsAdmin ? "Failed — Needs Admin" : "Failed";
                item.NextStep = needsAdmin
                    ? "Restart as Administrator → Clean"
                    : "Retry Clean (close locking apps / reboot if needed)";
                continue;
            }
            if (kind == "ephemeral")
            {
                item.Status = "Cleaned";
                item.NextStep = "Verifying…";
            }
            else if (kind == "sticky")
            {
                item.Status = "Applied";
                item.NextStep = "Verifying…";
            }
            else
            {
                item.Status = "Done";
                item.NextStep = "Verifying…";
            }
        }
    }

    public static Dictionary<string, int> Verify(IReadOnlyList<ModuleResult> cleanResults, IReadOnlyDictionary<string, ModuleResult> verified, bool admin)
    {
        var counts = new Dictionary<string, int>();
        foreach (var result in cleanResults)
        {
            var kind = ModuleKind.GetValueOrDefault(result.ModuleId, "ephemeral");
            verified.TryGetValue(result.ModuleId, out var follow);
            var remaining = follow?.Items.Select(i => i.Id).ToHashSet() ?? [];
            foreach (var item in result.Items)
            {
                var gone = !remaining.Contains(item.Id);
                if (FailStatuses.Contains(item.Status ?? "") || (item.Status ?? "").StartsWith("Failed", StringComparison.Ordinal))
                {
                    if (gone)
                    {
                        item.Status = "Fixed";
                        item.NextStep = "Verified — no longer detected";
                    }
                    else if (item.Status?.Contains("Admin", StringComparison.Ordinal) != true && kind != "sticky")
                    {
                        item.Status = "Still present";
                        item.NextStep = "Still on disk — close apps / reboot, or Clean again";
                    }
                }
                else if (gone)
                {
                    item.Status = "Fixed";
                    item.NextStep = kind switch
                    {
                        "sticky" => "Verified fixed — should stay off",
                        "maintenance" => "Verified done — safe to run again anytime",
                        _ => "Verified cleared (may refill later — normal)",
                    };
                }
                else if (kind == "sticky")
                {
                    item.Status = "Not fixed";
                    item.NextStep = admin
                        ? "Still detected — retry Clean or reboot"
                        : "Still detected — Restart as Administrator → Clean";
                }
                else if (kind == "maintenance")
                {
                    item.Status = "Done";
                    item.NextStep = "Flush ran — cache refills while browsing (normal)";
                }
                else
                {
                    item.Status = "Still present";
                    item.NextStep = "Still on disk — close apps / reboot, or Clean again (Needs Admin if path is system-protected)";
                }
                var key = string.IsNullOrEmpty(item.Status) ? "?" : item.Status;
                counts[key] = counts.GetValueOrDefault(key) + 1;
            }
        }
        return counts;
    }

    public static void Record(IReadOnlyList<ModuleResult> results, bool dryRun, bool admin, IReadOnlyList<string> skippedIds)
    {
        if (dryRun)
            return;
        var prev = LoadHistory();
        var items = prev["items"] as JsonObject ?? new JsonObject();
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        foreach (var result in results)
        {
            var kind = ModuleKind.GetValueOrDefault(result.ModuleId, "ephemeral");
            foreach (var item in result.Items)
            {
                var status = item.Status ?? "";
                var low = status.ToLowerInvariant();
                JsonObject entry;
                if (status is "Fixed" or "Cleaned" or "Applied" or "Done" || low.StartsWith("cleaned", StringComparison.Ordinal))
                {
                    entry = Entry(true, result.ModuleId, item, kind, status == "Fixed" ? "verified" : "applied", status, now);
                }
                else if (status == "Still present" && kind == "ephemeral")
                {
                    entry = Entry(false, result.ModuleId, item, kind, "partial", status, now);
                }
                else
                {
                    var needs = low.Contains("admin") || item.RequiresAdmin || AdminModules.Contains(result.ModuleId);
                    entry = Entry(false, result.ModuleId, item, kind, needs && !admin ? "needs_admin" : "failed", status, now);
                }
                items[Key(result.ModuleId, item.Id)] = entry;
            }
        }
        foreach (var mid in skippedIds)
        {
            items[Key(mid, "__module_skipped__")] = new JsonObject
            {
                ["ok"] = false,
                ["module_id"] = mid,
                ["item_id"] = "__module_skipped__",
                ["kind"] = ModuleKind.GetValueOrDefault(mid, "ephemeral"),
                ["reason"] = "needs_admin",
                ["when"] = now,
            };
        }
        var skipped = new JsonArray();
        foreach (var id in skippedIds)
            skipped.Add(id);
        SaveHistory(new JsonObject
        {
            ["version"] = 1,
            ["when"] = now,
            ["admin"] = admin,
            ["skipped_modules"] = skipped,
            ["items"] = items,
        });
    }

    private static JsonObject Entry(bool ok, string moduleId, CleanItem item, string kind, string reason, string status, long when) => new()
    {
        ["ok"] = ok,
        ["module_id"] = moduleId,
        ["item_id"] = item.Id,
        ["label"] = item.Label,
        ["kind"] = kind,
        ["reason"] = reason,
        ["when"] = when,
        ["status"] = status,
    };

    private static void AnnotateScanItem(string moduleId, CleanItem item, string kind, JsonObject? hist, bool admin, bool moduleSkipped)
    {
        var needs = (item.RequiresAdmin && !admin) || (AdminModules.Contains(moduleId) && !admin) || (moduleSkipped && !admin);
        if (hist is not null)
        {
            var ok = hist["ok"]?.GetValue<bool>() == true;
            var reason = hist["reason"]?.GetValue<string>() ?? "";
            if (ok)
            {
                if (kind == "ephemeral")
                {
                    item.Status = "Came back";
                    item.NextStep = "Normal refill — Clean again only if you want more space";
                    return;
                }
                if (kind == "sticky")
                {
                    item.Status = "Still open";
                    item.NextStep = "Did not stick — Restart as Administrator → Clean";
                    return;
                }
                item.Status = "Ready again";
                item.NextStep = "Optional — Clean anytime";
                return;
            }
            if (reason == "needs_admin" || needs)
            {
                item.Status = "Needs Admin";
                item.NextStep = "Restart as Administrator → Clean";
                return;
            }
            if (reason == "partial")
            {
                item.Status = "Still present";
                item.NextStep = "Close locking apps / reboot, then Clean again";
                return;
            }
            item.Status = "Failed before";
            item.NextStep = "Retry Clean (as Administrator if required)";
            return;
        }
        if (needs)
        {
            item.Status = "Needs Admin";
            item.NextStep = "Restart as Administrator → Clean (or it will keep showing)";
            return;
        }
        if (kind == "sticky")
        {
            item.Status = "Ready";
            item.NextStep = "Clean to apply — should stay off after success";
            return;
        }
        if (kind == "maintenance")
        {
            item.Status = "Ready";
            item.NextStep = "Optional flush — safe anytime";
            return;
        }
        item.Status = "Ready";
        item.NextStep = "Clean to free space (may refill later — normal)";
    }

    private static List<string> ErrorsFor(CleanItem item, IReadOnlyList<string> errors)
    {
        var id = (item.Id ?? "").ToLowerInvariant();
        if (id.Length == 0)
            return [];
        var prefix = id + ":";
        var bare = id.Contains(':') ? id.Split(':', 2)[1] : "";
        var detail = (item.Detail ?? "").ToLowerInvariant();
        var detailIsPath = detail.StartsWith("c:\\") || detail.StartsWith("d:\\") || detail.StartsWith("e:\\") || detail.StartsWith('%') || detail.StartsWith('/');
        var matched = new List<string>();
        foreach (var err in errors)
        {
            var el = err.ToLowerInvariant();
            if (el.StartsWith(prefix, StringComparison.Ordinal) || (" " + el).Contains(" " + prefix, StringComparison.Ordinal))
            {
                matched.Add(err);
                continue;
            }
            if (el.Contains(id, StringComparison.Ordinal) && (el.StartsWith(id, StringComparison.Ordinal) || el.Contains(id + ":", StringComparison.Ordinal) || el.Contains("(" + id + ")", StringComparison.Ordinal) || (" " + el + " ").Contains(" " + id + " ", StringComparison.Ordinal)))
            {
                matched.Add(err);
                continue;
            }
            if (bare.Length >= 4 && (el.StartsWith(bare + ":", StringComparison.Ordinal) || el.Contains("service " + bare, StringComparison.Ordinal) || el.Contains("task " + bare, StringComparison.Ordinal) || (" " + el).Contains(" " + bare + ":", StringComparison.Ordinal)))
            {
                matched.Add(err);
                continue;
            }
            if (detailIsPath && detail.Length > 0 && el.Contains(detail, StringComparison.Ordinal))
                matched.Add(err);
        }
        return matched;
    }

    private static bool LooksAdmin(string? text)
    {
        var t = (text ?? "").ToLowerInvariant();
        return t.Contains("needs administrator") || t.Contains("access is denied") || t.Contains("access denied")
            || t.Contains("denied") || t.Contains("privilege") || t.Contains("elevat");
    }
}
