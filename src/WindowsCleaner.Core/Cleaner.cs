namespace WindowsCleaner;

public static class ModuleCatalog
{
    public static readonly HashSet<string> OptIn =
    [
        "bloatware", "bloatware_oem", "perf_services", "startup_apps", "startup_services",
        "ai_caches", "ai_history", "ai_models", "browser_privacy", "system_reclaim",
        "driver_store", "dev_disks", "windows_features",
    ];

    public static readonly HashSet<string> ManualPreset =
    [
        "perf_services", "startup_services", "ai_history", "ai_models",
        "system_reclaim", "driver_store", "dev_disks", "windows_features",
    ];

    public static readonly string[] ProfileNames =
    [
        "safe", "standard", "privacy", "oem", "disk", "new_pc", "debloat", "ai", "workstation", "full",
    ];

    private static readonly HashSet<string> Disk =
    [
        "temp_files", "recycle_bin", "browser_caches", "gpu_caches", "caches", "logs",
        "app_caches", "dev_caches", "ai_caches",
    ];

    private static readonly HashSet<string> NewPc =
        ["privacy", "tracking", "telemetry_services", "bloatware", "bloatware_oem"];

    private static readonly HashSet<string> Debloat =
        ["bloatware", "bloatware_oem", "startup_services", "windows_features"];

    private static readonly HashSet<string> Ai = ["ai_caches", "ai_history"];

    public static List<CleanModule> All() =>
    [
        new TempFilesModule(),
        new RecycleBinModule(),
        new BrowserCachesModule(),
        new BrowserPrivacyModule(),
        new GpuCachesModule(),
        new CachesModule(),
        new AppCachesModule(),
        new DevCachesModule(),
        new LogsModule(),
        new TrackingModule(),
        new NetworkCacheModule(),
        new PrivacyModule(),
        new TelemetryServicesModule(),
        new StartupAppsModule(),
        new BloatwareModule(),
        new BloatwareOemModule(),
        new StartupServicesModule(),
        new PerfServicesModule(),
        new AiCachesModule(),
        new AiHistoryModule(),
        new AiModelsModule(),
        new DevDisksModule(),
        new SystemReclaimModule(),
        new DriverStoreModule(),
        new WindowsFeaturesModule(),
    ];

    public static List<CleanModule> Select(IEnumerable<string>? only, IEnumerable<string>? exclude, string profile)
    {
        var onlySet = new HashSet<string>((only ?? []).Select(s => s.Trim()).Where(s => s.Length > 0));
        var excludeSet = new HashSet<string>((exclude ?? []).Select(s => s.Trim()).Where(s => s.Length > 0));
        var selected = new List<CleanModule>();
        foreach (var mod in All())
        {
            if (onlySet.Count > 0)
            {
                if (onlySet.Contains(mod.Id) && !excludeSet.Contains(mod.Id))
                    selected.Add(mod);
                continue;
            }
            if (excludeSet.Contains(mod.Id))
                continue;
            var take = profile switch
            {
                "safe" => mod.Risk == Risk.Safe && mod.DefaultEnabled,
                "privacy" => mod.Id is "privacy" or "tracking" or "telemetry_services",
                "oem" => mod.Id is "bloatware" or "bloatware_oem",
                "disk" or "workstation" => Disk.Contains(mod.Id),
                "new_pc" => NewPc.Contains(mod.Id),
                "debloat" => Debloat.Contains(mod.Id),
                "ai" => Ai.Contains(mod.Id),
                "full" => !ManualPreset.Contains(mod.Id),
                _ => mod.DefaultEnabled && !OptIn.Contains(mod.Id),
            };
            if (take)
                selected.Add(mod);
        }
        return selected;
    }
}

public sealed class Cleaner
{
    public Cleaner(IReadOnlyList<CleanModule> modules) => Modules = modules;
    public IReadOnlyList<CleanModule> Modules { get; }

    public CleanReport Scan(Action<string>? progress)
    {
        var report = new CleanReport { Admin = Admin.IsAdmin() };
        var history = ItemStatus.LoadHistory();
        var results = new ModuleResult[Modules.Count];
        Parallel.For(0, Modules.Count, new ParallelOptions { MaxDegreeOfParallelism = 4 }, i =>
        {
            var mod = Modules[i];
            progress?.Invoke($"Scanning: {mod.Label}");
            try
            {
                var result = mod.Scan(progress);
                ItemText.Enrich(result);
                foreach (var item in result.Items)
                {
                    if (string.IsNullOrEmpty(item.Risk))
                        item.Risk = RiskText.Of(mod.Risk);
                }
                ItemStatus.AnnotateScan(result, history);
                results[i] = result;
            }
            catch (Exception ex)
            {
                var failed = new ModuleResult { ModuleId = mod.Id, Label = mod.Label };
                failed.Errors.Add(ex.Message);
                results[i] = failed;
            }
        });
        report.Results.AddRange(results);
        return report;
    }

    public CleanReport Clean(bool dryRun, Action<string>? progress, IReadOnlyDictionary<string, IReadOnlySet<string>>? onlyIds, bool includeUnchecked)
    {
        var report = new CleanReport { DryRun = dryRun, Admin = Admin.IsAdmin() };
        var cleaned = new List<CleanModule>();
        foreach (var mod in Modules)
        {
            progress?.Invoke($"{(dryRun ? "Dry-run" : "Cleaning")}: {mod.Label}");
            IReadOnlySet<string>? modOnly = null;
            if (onlyIds is not null)
                modOnly = onlyIds.TryGetValue(mod.Id, out var ids) ? ids : new HashSet<string>();
            try
            {
                var result = mod.Clean(dryRun, progress, modOnly, includeUnchecked);
                ItemText.Enrich(result);
                foreach (var item in result.Items)
                {
                    if (string.IsNullOrEmpty(item.Risk))
                        item.Risk = RiskText.Of(mod.Risk);
                }
                ItemStatus.AnnotateClean(result, dryRun, report.Admin);
                report.Results.Add(result);
                cleaned.Add(mod);
                if (!dryRun && !report.Admin && mod.RequiresAdmin && result.Items.Count > 0 &&
                    result.Items.All(i => (i.Status ?? "").StartsWith("Failed", StringComparison.Ordinal) || i.Status == "Needs Admin"))
                {
                    report.SkippedModules.Add($"{mod.Label} (needs Administrator)");
                    report.SkippedModuleIds.Add(mod.Id);
                }
            }
            catch (Exception ex)
            {
                var failed = new ModuleResult { ModuleId = mod.Id, Label = mod.Label, DryRun = dryRun };
                failed.Errors.Add(ex.Message);
                report.Results.Add(failed);
            }
        }

        if (!dryRun && cleaned.Count > 0)
        {
            progress?.Invoke("Verifying fixes (re-scan)...");
            var verified = new Dictionary<string, ModuleResult>();
            foreach (var mod in cleaned)
            {
                progress?.Invoke($"Verifying: {mod.Label}");
                try
                {
                    verified[mod.Id] = mod.Scan(progress);
                    ItemText.Enrich(verified[mod.Id]);
                }
                catch (Exception ex)
                {
                    var empty = new ModuleResult { ModuleId = mod.Id, Label = mod.Label };
                    empty.Errors.Add($"verify failed: {ex.Message}");
                    verified[mod.Id] = empty;
                }
            }
            report.VerifyCounts = ItemStatus.Verify(report.Results, verified, report.Admin);
        }
        if (!dryRun)
            ItemStatus.Record(report.Results, dryRun: false, report.Admin, report.SkippedModuleIds);
        return report;
    }
}
