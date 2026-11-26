namespace WindowsCleaner;

public sealed class PathPlan
{
    public required string Id { get; init; }
    public required string Label { get; init; }
    public List<string> Paths { get; init; } = [];
    public bool DefaultInclude { get; init; } = true;
    public bool RequiresAdmin { get; init; }
    public string Effect { get; init; } = "";
    public string Repercussions { get; init; } = "";
    public int? MaxFiles { get; init; }
}

public static class PathRows
{
    public static long SizeOf(PathPlan plan)
    {
        long total = 0;
        foreach (var path in plan.Paths)
            total += plan.MaxFiles is null ? Sizes.PathSize(path) : Sizes.PathSize(path, plan.MaxFiles.Value);
        return total;
    }

    public static List<PathPlan> Select(IEnumerable<PathPlan> plans, IReadOnlySet<string>? onlyIds, bool includeUnchecked)
    {
        var chosen = plans.Where(p => ItemFilter.Allow(p.Id, onlyIds)).ToList();
        if (onlyIds is null && !includeUnchecked)
            chosen = chosen.Where(p => p.DefaultInclude).ToList();
        return chosen;
    }

    public static ModuleResult Scan(CleanModule module, IEnumerable<PathPlan> plans, Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = module.Id, Label = module.Label };
        foreach (var plan in plans)
        {
            progress?.Invoke($"Scanning {plan.Label}");
            var existing = plan.Paths.Where(Fs.Exists).ToList();
            if (existing.Count == 0)
                continue;
            var size = SizeOf(new PathPlan { Id = plan.Id, Label = plan.Label, Paths = existing, MaxFiles = plan.MaxFiles });
            if (size <= 0)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = plan.Id,
                Label = plan.Label,
                Detail = Detail(existing),
                BytesEstimate = size,
                RequiresAdmin = plan.RequiresAdmin,
                Effect = plan.Effect,
                Repercussions = plan.Repercussions,
                DefaultInclude = plan.DefaultInclude,
                Risk = RiskText.Of(module.Risk),
            });
        }
        return result;
    }

    public static ModuleResult Clean(CleanModule module, IReadOnlyList<PathPlan> plans, bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked)
    {
        var chosen = Select(plans, onlyIds, includeUnchecked);
        if (dryRun)
        {
            var preview = Scan(module, chosen, progress);
            preview.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
            if (onlyIds is null && !includeUnchecked)
                preview.Items.RemoveAll(i => !i.DefaultInclude);
            preview.DryRun = true;
            preview.BytesFreed = preview.BytesEstimate;
            foreach (var item in preview.Items)
                preview.Actions.Add($"Would clean {item.Label}");
            return preview;
        }
        var result = new ModuleResult { ModuleId = module.Id, Label = module.Label };
        var deleted = new List<DeleteResult>();
        foreach (var plan in chosen)
        {
            var existing = plan.Paths.Where(Fs.Exists).ToList();
            if (existing.Count == 0)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = plan.Id,
                Label = plan.Label,
                Detail = Detail(existing),
                RequiresAdmin = plan.RequiresAdmin,
                Effect = plan.Effect,
                Repercussions = plan.Repercussions,
                DefaultInclude = plan.DefaultInclude,
                Risk = RiskText.Of(module.Risk),
            });
            progress?.Invoke($"Cleaning {plan.Label}");
            foreach (var path in existing)
                deleted.Add(Fs.DeletePath(path, dryRun: false));
            result.Actions.Add($"Cleaned {plan.Label}");
        }
        if (deleted.Count > 0)
        {
            var merged = Fs.Merge(deleted);
            result.BytesFreed = merged.BytesFreed;
            result.Errors.AddRange(merged.Errors);
        }
        return result;
    }

    private static string Detail(IReadOnlyList<string> paths)
    {
        var shown = paths.Take(4).ToList();
        var text = string.Join("; ", shown);
        var extra = paths.Count - shown.Count;
        return extra > 0 ? text + $"; +{extra} more" : text;
    }
}

public sealed class TempFilesModule : CleanModule
{
    public override string Id => "temp_files";
    public override string Label => "Temporary Files";
    public override string Description => "User and system TEMP folders, recent-docs shortcuts, Internet cache leftovers, and user crash dumps.";

    private static List<(string Id, string Path, bool Admin)> Targets()
    {
        var userTemp = Path.GetFullPath(Paths.Temp());
        var local = Paths.Local();
        var windir = Paths.WindowsDir();
        var rows = new List<(string, string, bool)>
        {
            ("user_temp", userTemp, false),
            ("windows_temp", Path.GetFullPath(Path.Combine(windir, "Temp")), true),
            ("recent", Path.Combine(Paths.Roaming(), @"Microsoft\Windows\Recent"), false),
        };
        var tmp = Environment.GetEnvironmentVariable("TMP");
        if (!string.IsNullOrEmpty(tmp))
        {
            try
            {
                var full = Path.GetFullPath(tmp);
                if (!full.Equals(userTemp, StringComparison.OrdinalIgnoreCase))
                    rows.Add(("tmp_env", full, false));
            }
            catch (IOException) { }
        }
        if (!string.IsNullOrEmpty(local))
        {
            rows.Add(("iedownload", Path.Combine(local, @"Microsoft\Windows\INetCache"), false));
            rows.Add(("wer_user", Path.Combine(local, @"Microsoft\Windows\WER"), false));
            rows.Add(("minidump_user", Path.Combine(local, "CrashDumps"), false));
        }
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        return rows.Where(r => seen.Add(r.Item2)).ToList();
    }

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        foreach (var (id, path, admin) in Targets())
        {
            progress?.Invoke($"Scanning {path}");
            if (!Fs.Exists(path))
                continue;
            var size = Sizes.PathSize(path);
            if (size <= 0)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = id,
                Label = string.IsNullOrEmpty(Path.GetFileName(path)) ? path : Path.GetFileName(path),
                Detail = path,
                BytesEstimate = size,
                RequiresAdmin = admin,
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        if (dryRun)
        {
            var preview = Scan(progress);
            preview.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
            preview.DryRun = true;
            preview.BytesFreed = preview.BytesEstimate;
            foreach (var item in preview.Items)
                preview.Actions.Add($"Would free from {item.Detail}");
            return preview;
        }
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        var admin = Admin.IsAdmin();
        var parts = new List<DeleteResult>();
        foreach (var (id, path, needs) in Targets())
        {
            if (!ItemFilter.Allow(id, onlyIds) || !Fs.Exists(path))
                continue;
            var item = new CleanItem { Id = id, Label = Path.GetFileName(path), Detail = path, RequiresAdmin = needs };
            result.Items.Add(item);
            if (needs && !admin)
            {
                item.Detail = "Needs Administrator - not cleaned (will show again on Scan)";
                result.Errors.Add($"{id}: needs Administrator");
                continue;
            }
            progress?.Invoke($"Clearing {path}");
            var cleared = Fs.ClearDirectory(path, dryRun: false);
            parts.Add(cleared);
            result.Actions.Add($"Freed from {path}");
            result.Errors.AddRange(cleared.Errors);
        }
        if (parts.Count > 0)
            result.BytesFreed = Fs.Merge(parts).BytesFreed;
        return result;
    }
}

public sealed class RecycleBinModule : CleanModule
{
    public override string Id => "recycle_bin";
    public override string Label => "Recycle Bin";
    public override string Description => "Permanently empties the Recycle Bin for all drives.";

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Querying Recycle Bin…");
        var size = ShellUi.RecycleBinBytes();
        if (size > 0)
            result.Items.Add(new CleanItem { Id = "recycle_bin", Label = "Recycle Bin", Detail = "All drives", BytesEstimate = size });
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
        result.DryRun = dryRun;
        if (result.Items.Count == 0)
            return result;
        var size = result.Items[0].BytesEstimate;
        if (dryRun)
        {
            result.BytesFreed = size;
            result.Actions.Add($"Would empty Recycle Bin (~{size} bytes)");
            return result;
        }
        progress?.Invoke("Emptying Recycle Bin…");
        var hr = ShellUi.EmptyRecycleBin();
        if (hr is 0 or unchecked((int)0x8000FFFF))
        {
            result.BytesFreed = size;
            result.Actions.Add("Emptied Recycle Bin");
        }
        else
            result.Errors.Add($"SHEmptyRecycleBin failed: HRESULT 0x{hr:X8}");
        return result;
    }
}

public sealed class GpuCachesModule : CleanModule
{
    public override string Id => "gpu_caches";
    public override string Label => "GPU / Shader Caches";
    public override string Description => "Clears DirectX / NVIDIA / AMD / Intel shader caches. Safe; games may hitch briefly while shaders rebuild.";

    private static List<(string Id, string Label, string Path)> Targets()
    {
        var local = Paths.Local();
        return
        [
            ("d3d", "Direct3D shader cache", Path.Combine(local, "D3DSCache")),
            ("dxcache", "DXCache", Path.Combine(local, "Microsoft", "DXCache")),
            ("nvidia_gl", "NVIDIA GL cache", Path.Combine(local, "NVIDIA", "GLCache")),
            ("nvidia_dx", "NVIDIA DX cache", Path.Combine(local, "NVIDIA", "DXCache")),
            ("amd_dx", "AMD DX cache", Path.Combine(local, "AMD", "DxCache")),
            ("amd_gl", "AMD GL cache", Path.Combine(local, "AMD", "GLCache")),
            ("intel", "Intel shader cache", Path.Combine(local, "Intel", "ShaderCache")),
        ];
    }

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        foreach (var (id, label, path) in Targets())
        {
            progress?.Invoke($"Scanning {label}");
            var size = Sizes.PathSize(path);
            if (size > 0)
                result.Items.Add(new CleanItem { Id = id, Label = label, Detail = path, BytesEstimate = size });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        if (dryRun)
        {
            var preview = Scan(progress);
            preview.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
            preview.DryRun = true;
            preview.BytesFreed = preview.BytesEstimate;
            foreach (var item in preview.Items)
                preview.Actions.Add($"Would clean {item.Label}");
            return preview;
        }
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        var parts = new List<DeleteResult>();
        foreach (var (id, label, path) in Targets())
        {
            if (!ItemFilter.Allow(id, onlyIds) || !Fs.Exists(path))
                continue;
            result.Items.Add(new CleanItem { Id = id, Label = label, Detail = path });
            progress?.Invoke($"Cleaning {label}");
            parts.Add(Fs.ClearDirectory(path, false));
            result.Actions.Add($"Cleaned {label}");
        }
        if (parts.Count > 0)
        {
            var merged = Fs.Merge(parts);
            result.BytesFreed = merged.BytesFreed;
            result.Errors.AddRange(merged.Errors);
        }
        return result;
    }
}

public sealed class NetworkCacheModule : CleanModule
{
    public override string Id => "network_cache";
    public override string Label => "DNS / Network Cache";
    public override string Description => "Flushes the DNS resolver cache (ipconfig /flushdns). Entries refill as you browse.";

    public override ModuleResult Scan(Action<string>? progress)
    {
        progress?.Invoke("DNS cache is a flush action (not sized junk)");
        return new ModuleResult { ModuleId = Id, Label = Label };
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label, DryRun = dryRun };
        if (!ItemFilter.Allow("flushdns", onlyIds))
            return result;
        result.Items.Add(new CleanItem { Id = "flushdns", Label = "DNS resolver cache", Detail = "ipconfig /flushdns (refills as you browse)" });
        if (dryRun)
        {
            result.Actions.Add("Would flush DNS cache");
            return result;
        }
        progress?.Invoke("Flushing DNS cache...");
        var proc = Proc.Run(["ipconfig", "/flushdns"]);
        if (proc.ExitCode == 0)
            result.Actions.Add("Flushed DNS resolver cache (will refill while browsing)");
        else
            result.Errors.Add(string.IsNullOrWhiteSpace(proc.Tail) ? "flushdns failed" : proc.Tail);
        return result;
    }
}
