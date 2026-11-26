using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

namespace WindowsCleaner;

public static class SystemParsers
{
    private static readonly Regex SizeRe = new(@"([\d.]+)\s*(TB|GB|MB|KB|B)\b", RegexOptions.IgnoreCase);
    private static readonly Dictionary<string, long> Units = new(StringComparer.OrdinalIgnoreCase)
    {
        ["B"] = 1, ["KB"] = 1024, ["MB"] = 1024L * 1024, ["GB"] = 1024L * 1024 * 1024, ["TB"] = 1024L * 1024 * 1024 * 1024,
    };

    public static long ToBytes(double number, string unit) => (long)(number * Units[unit.ToUpperInvariant()]);

    public static long ParseComponentStore(string text)
    {
        long total = 0;
        foreach (var line in text.Split('\n'))
        {
            var low = line.ToLowerInvariant();
            if (!low.Contains("backup") && !low.Contains("cache and temporary") && !low.Contains("reclaimable"))
                continue;
            var match = SizeRe.Match(line);
            if (match.Success)
                total += ToBytes(double.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture), match.Groups[2].Value);
        }
        return total;
    }

    public static (long Used, long? Maximum) ParseShadow(string text)
    {
        long used = 0;
        long? maximum = 0;
        foreach (var line in text.Split('\n'))
        {
            var low = line.ToLowerInvariant();
            var match = SizeRe.Match(line);
            if (low.Contains("used shadow copy storage") && match.Success)
                used = ToBytes(double.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture), match.Groups[2].Value);
            else if (low.Contains("maximum shadow copy storage"))
            {
                if (low.Contains("unbounded"))
                    maximum = null;
                else if (match.Success)
                    maximum = ToBytes(double.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture), match.Groups[2].Value);
            }
        }
        return (used, maximum);
    }

    public static bool ShadowShouldShrink(long used, long? maximum)
    {
        if (used < 100L * 1024 * 1024)
            return false;
        if (maximum is null)
            return true;
        return maximum > Math.Max(used * 2, 2L * 1024 * 1024 * 1024);
    }

    public static List<string> ShadowResize(long used, string? drive = null)
    {
        drive ??= Paths.SystemDrive();
        var megabytes = Math.Max(320, Math.Max(used / 2, 320L * 1024 * 1024) / (1024 * 1024));
        return ["vssadmin", "resize", "shadowstorage", $"/for={drive}", $"/on={drive}", $"/maxsize={megabytes}MB"];
    }

    public sealed record DriverPkg(string Published, string Provider, string ClassName, string Version, string Original);

    public static List<DriverPkg> ParseDrivers(string text)
    {
        var packages = new List<DriverPkg>();
        foreach (var block in Regex.Split(text, @"(?=Published Name:\s*)", RegexOptions.IgnoreCase))
        {
            var published = Field(block, "Published Name");
            if (published.Length == 0)
                continue;
            packages.Add(new DriverPkg(published, Field(block, "Provider Name"), Field(block, "Class Name"), Field(block, "Driver Version"), Field(block, "Original Name")));
        }
        return packages;
    }

    public static HashSet<string> InUse(string text) =>
        TextMatch.OemInf().Matches(text).Select(m => m.Value.ToLowerInvariant()).ToHashSet();

    public static List<DriverPkg> Superseded(IEnumerable<DriverPkg> packages, IEnumerable<string> inUse)
    {
        var used = inUse.Select(n => n.ToLowerInvariant()).ToHashSet();
        return packages.Where(p =>
        {
            var name = p.Published.ToLowerInvariant();
            return name.StartsWith("oem") && name.EndsWith(".inf") && !used.Contains(name);
        }).ToList();
    }

    private static string Field(string block, string label)
    {
        var match = Regex.Match(block, Regex.Escape(label) + @":\s*(.+)", RegexOptions.IgnoreCase);
        return match.Success ? match.Groups[1].Value.Trim() : "";
    }

    private static readonly Regex LangTag = new(@"~~~([a-z]{2,3}(?:-[a-zA-Z0-9]+)?)~", RegexOptions.IgnoreCase);
    private static readonly (string Prefix, string Label)[] Capabilities = [("XPS.Viewer", "XPS Viewer"), ("App.StepsRecorder", "Steps Recorder"), ("Media.WindowsMediaPlayer", "Windows Media Player")];
    private static readonly Dictionary<string, string> Features = new()
    {
        ["Printing-XPSServices-Features"] = "XPS Services",
        ["WindowsMediaPlayer"] = "Windows Media Player",
    };

    public static string? CapabilityLanguage(string name)
    {
        if (!name.StartsWith("language.", StringComparison.OrdinalIgnoreCase))
            return null;
        var match = LangTag.Match(name);
        return match.Success ? match.Groups[1].Value : null;
    }

    public static List<(string Id, string Label)> SelectableFeatures(IEnumerable<string> names, IReadOnlySet<string> keepTags)
    {
        var keep = keepTags.Select(t => t.ToLowerInvariant()).ToHashSet();
        var chosen = new List<(string, string)>();
        foreach (var name in names)
        {
            if (Features.TryGetValue(name, out var feature))
            {
                chosen.Add(($"feature:{name}", feature));
                continue;
            }
            var hit = false;
            foreach (var (prefix, label) in Capabilities)
            {
                if (name.StartsWith(prefix, StringComparison.Ordinal))
                {
                    chosen.Add(($"capability:{name}", label));
                    hit = true;
                    break;
                }
            }
            if (hit)
                continue;
            var tag = CapabilityLanguage(name);
            if (tag is not null && !keep.Contains(tag.ToLowerInvariant()))
                chosen.Add(($"capability:{name}", $"Language pack {tag}"));
        }
        return chosen;
    }

    public static HashSet<string> UiLanguages()
    {
        var tags = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var id in new[] { GetUserDefaultUILanguage(), GetSystemDefaultUILanguage() })
        {
            try
            {
                var name = CultureInfo.GetCultureInfo(id).Name;
                if (!string.IsNullOrEmpty(name))
                    tags.Add(name);
            }
            catch (CultureNotFoundException) { }
        }
        return tags;
    }

    [DllImport("kernel32.dll")] private static extern ushort GetUserDefaultUILanguage();
    [DllImport("kernel32.dll")] private static extern ushort GetSystemDefaultUILanguage();
}

public sealed class SystemReclaimModule : CleanModule
{
    public override string Id => "system_reclaim";
    public override string Label => "System Disk Reclaim";
    public override string Description => "Component store cleanup, hibernation file, a smaller System Restore cap, and leftover Windows upgrade folders. ResetBase stays unchecked.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Analyzing component store");
        var analyze = Proc.Run([Path.Combine(Paths.System32(), "Dism.exe"), "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"], 300_000);
        var text = analyze.Stdout + "\n" + analyze.Stderr;
        var reclaim = SystemParsers.ParseComponentStore(text);
        if (reclaim > 0)
        {
            result.Items.Add(new CleanItem
            {
                Id = "component_store",
                Label = "Component store cleanup",
                Detail = analyze.ExitCode != 0 ? "Needs Administrator to measure the component store" : "DISM AnalyzeComponentStore",
                BytesEstimate = reclaim,
                RequiresAdmin = true,
                Effect = "Removes superseded Windows update files from WinSxS.",
                Repercussions = "Slow, and needs Administrator. Windows Update keeps working. This row does not use /ResetBase.",
            });
            result.Items.Add(new CleanItem
            {
                Id = "component_store_resetbase",
                Label = "Component store cleanup with ResetBase",
                Detail = "Unchecked. /ResetBase blocks uninstalling the cleaned updates.",
                BytesEstimate = reclaim,
                RequiresAdmin = true,
                DefaultInclude = false,
                Effect = "Runs component-store cleanup with /ResetBase.",
                Repercussions = "Windows can no longer uninstall the updates this removes. Leave this unchecked unless you accept that.",
            });
        }
        var hiber = Path.Combine(Paths.SystemDrive() + "\\", "hiberfil.sys");
        var hiberSize = Sizes.PathSize(hiber);
        if (hiberSize > 0)
        {
            result.Items.Add(new CleanItem
            {
                Id = "hiberfil",
                Label = "Hibernation file",
                Detail = $"{hiber} — turning hibernation off also turns off Fast Startup.",
                BytesEstimate = hiberSize,
                RequiresAdmin = true,
                Effect = "Turns hibernation off and removes hiberfil.sys.",
                Repercussions = "Fast Startup turns off too. Sleep still works. Turn hibernation back on with powercfg -h on if you need it.",
            });
        }
        progress?.Invoke("Reading shadow copy storage");
        var shadow = Proc.Run(["vssadmin", "list", "shadowstorage"], 60_000);
        var (used, maximum) = SystemParsers.ParseShadow(shadow.Stdout);
        if (SystemParsers.ShadowShouldShrink(used, maximum))
        {
            result.Items.Add(new CleanItem
            {
                Id = "shadow_copies",
                Label = "System Restore storage cap",
                Detail = maximum is null ? "Used shadow storage can shrink. Current cap is unlimited." : "Used shadow storage can shrink. Older restore points past the new cap may drop.",
                BytesEstimate = used / 2,
                RequiresAdmin = true,
                Effect = "Lowers the shadow-copy cap to about half of what is in use.",
                Repercussions = "Does not delete every restore point. System Restore stays on with a smaller ceiling.",
            });
        }
        foreach (var name in new[] { "$Windows.~BT", "$Windows.~WS" })
        {
            var path = Path.Combine(Paths.SystemDrive() + "\\", name);
            var size = Fs.Exists(path) ? Sizes.PathSize(path) : 0;
            if (size <= 0)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"upgrade:{name}",
                Label = $"Upgrade leftover {name}",
                Detail = path,
                BytesEstimate = size,
                RequiresAdmin = true,
                Effect = "Deletes this leftover Windows setup folder.",
                Repercussions = "Same family as Windows.old. The folder is how a failed setup rolls back.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.DryRun = dryRun;
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds) || (onlyIds is null && !includeUnchecked && !i.DefaultInclude));
        if (dryRun)
        {
            result.BytesFreed = result.BytesEstimate;
            foreach (var item in result.Items)
                result.Actions.Add($"Would clean {item.Label}");
            return result;
        }
        var admin = Admin.IsAdmin();
        var resetbase = result.Items.Any(i => i.Id == "component_store_resetbase");
        var ran = false;
        foreach (var item in result.Items)
        {
            progress?.Invoke($"Cleaning {item.Label}");
            if (!admin)
            {
                item.Detail = "Needs Administrator - not applied (will show again on Scan)";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            if (item.Id is "component_store" or "component_store_resetbase")
            {
                if (ran)
                {
                    result.Actions.Add($"Included in DISM cleanup: {item.Label}");
                    continue;
                }
                var cmd = new List<string> { Path.Combine(Paths.System32(), "Dism.exe"), "/Online", "/Cleanup-Image", "/StartComponentCleanup" };
                if (resetbase)
                    cmd.Add("/ResetBase");
                var proc = Proc.Run(cmd, 60 * 60 * 1000);
                ran = true;
                if (proc.ExitCode == 0)
                    result.Actions.Add("Ran component store cleanup");
                else
                {
                    item.Detail = proc.Tail.Length > 500 ? proc.Tail[..500] : proc.Tail;
                    result.Errors.Add($"{item.Id}: {item.Detail}");
                }
            }
            else if (item.Id == "hiberfil")
            {
                var proc = Proc.Run(["powercfg", "-h", "off"], 120_000);
                if (proc.ExitCode == 0)
                    result.Actions.Add("Turned hibernation off");
                else
                {
                    item.Detail = proc.Tail;
                    result.Errors.Add($"{item.Id}: {proc.Tail}");
                }
            }
            else if (item.Id == "shadow_copies")
            {
                var proc = Proc.Run(SystemParsers.ShadowResize(Math.Max(item.BytesEstimate * 2, 320L * 1024 * 1024)), 180_000);
                if (proc.ExitCode == 0)
                    result.Actions.Add("Shrank shadow-copy cap");
                else
                {
                    item.Detail = proc.Tail;
                    result.Errors.Add($"{item.Id}: {proc.Tail}");
                }
            }
            else if (item.Id.StartsWith("upgrade:"))
            {
                var path = Path.Combine(Paths.SystemDrive() + "\\", item.Id.Split(':', 2)[1]);
                var deleted = Fs.DeletePath(path, false);
                result.BytesFreed += deleted.BytesFreed;
                result.Errors.AddRange(deleted.Errors);
                result.Actions.Add($"Deleted {path}");
            }
        }
        return result;
    }
}

public sealed class DriverStoreModule : CleanModule
{
    public override string Id => "driver_store";
    public override string Label => "Old Drivers";
    public override string Description => "Driver packages in the driver store that no connected device is using. The in-use driver is not listed. Removal is one-way.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        var pnputil = Path.Combine(Paths.System32(), "pnputil.exe");
        progress?.Invoke("Listing driver packages");
        var listed = Proc.Run([pnputil, "/enum-drivers"], 180_000);
        var devices = Proc.Run([pnputil, "/enum-devices", "/connected", "/drivers"], 180_000);
        foreach (var pkg in SystemParsers.Superseded(SystemParsers.ParseDrivers(listed.Stdout), SystemParsers.InUse(devices.Stdout)))
        {
            var provider = string.IsNullOrEmpty(pkg.Provider) ? "Unknown provider" : pkg.Provider;
            result.Items.Add(new CleanItem
            {
                Id = $"driver:{pkg.Published}",
                Label = $"{provider} {pkg.Published}",
                Detail = $"{(string.IsNullOrEmpty(pkg.Original) ? pkg.Published : pkg.Original)} — {pkg.ClassName} — {pkg.Version}. Not used by a connected device.",
                RequiresAdmin = true,
                Effect = $"Removes superseded driver package {pkg.Published} ({provider}).",
                Repercussions = "Does not remove the driver a connected device is using. Reinstall the vendor driver if hardware needs this package later.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
        result.DryRun = dryRun;
        if (dryRun)
        {
            foreach (var item in result.Items)
                result.Actions.Add($"Would remove {item.Label}");
            return result;
        }
        var admin = Admin.IsAdmin();
        var pnputil = Path.Combine(Paths.System32(), "pnputil.exe");
        foreach (var item in result.Items)
        {
            if (!admin)
            {
                item.Detail = "Needs Administrator - not removed (will show again on Scan)";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            var published = item.Id.Split(':', 2)[1];
            var proc = Proc.Run([pnputil, "/delete-driver", published, "/uninstall"], 180_000);
            if (proc.ExitCode == 0)
                result.Actions.Add($"Removed {published}");
            else
            {
                item.Detail = proc.Tail.Length > 500 ? proc.Tail[..500] : proc.Tail;
                result.Errors.Add($"{item.Id}: {item.Detail}");
            }
        }
        return result;
    }
}

public sealed class WindowsFeaturesModule : CleanModule
{
    public override string Id => "windows_features";
    public override string Label => "Languages & Optional Features";
    public override string Description => "Extra language packs, XPS Viewer, Steps Recorder, and legacy Windows Media Player. The current display language stays. SMB1, .NET, and Hyper-V are not offered.";
    public override Risk Risk => Risk.Moderate;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Listing Windows capabilities");
        var caps = Names("Get-WindowsCapability -Online | Where-Object State -eq Installed | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress");
        var features = Names("Get-WindowsOptionalFeature -Online | Where-Object State -eq Enabled | Select-Object -ExpandProperty FeatureName | ConvertTo-Json -Compress");
        foreach (var (id, label) in SystemParsers.SelectableFeatures(caps.Concat(features), SystemParsers.UiLanguages()))
        {
            result.Items.Add(new CleanItem
            {
                Id = id,
                Label = label,
                Detail = id.Split(':', 2)[1],
                RequiresAdmin = true,
                Effect = $"Removes optional Windows component: {label}.",
                Repercussions = "The current display language is not offered. Reinstall later from Settings. SMB1, .NET, and Hyper-V are not targets.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
        result.DryRun = dryRun;
        if (dryRun)
        {
            foreach (var item in result.Items)
                result.Actions.Add($"Would remove {item.Label}");
            return result;
        }
        var admin = Admin.IsAdmin();
        foreach (var item in result.Items)
        {
            if (!admin)
            {
                item.Detail = "Needs Administrator - not removed (will show again on Scan)";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            var name = item.Id.Split(':', 2)[1].Replace("'", "''");
            var script = item.Id.StartsWith("feature:")
                ? $"Disable-WindowsOptionalFeature -Online -FeatureName '{name}' -NoRestart | Out-Null"
                : $"Remove-WindowsCapability -Online -Name '{name}' | Out-Null";
            var proc = Proc.PowerShell(script, 30 * 60 * 1000);
            if (proc.ExitCode == 0)
                result.Actions.Add($"Removed {item.Label}");
            else
            {
                item.Detail = proc.Tail.Length > 500 ? proc.Tail[..500] : proc.Tail;
                result.Errors.Add($"{item.Id}: {item.Detail}");
            }
        }
        return result;
    }

    private static List<string> Names(string script)
    {
        var proc = Proc.PowerShell(script, 300_000);
        var raw = proc.Stdout.Trim();
        if (raw.Length == 0)
            return [];
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(raw);
            if (doc.RootElement.ValueKind == System.Text.Json.JsonValueKind.String)
                return [doc.RootElement.GetString() ?? ""];
            if (doc.RootElement.ValueKind == System.Text.Json.JsonValueKind.Array)
                return doc.RootElement.EnumerateArray().Select(e => e.GetString() ?? "").Where(s => s.Length > 0).ToList();
        }
        catch (System.Text.Json.JsonException) { }
        return [];
    }
}

public sealed class DevDisksModule : CleanModule
{
    public override string Id => "dev_disks";
    public override string Label => "Developer Disks";
    public override string Description => "Docker build-cache prune and WSL ext4.vhdx compact. Every row starts unchecked. Does not delete the distro.";
    public override Risk Risk => Risk.Aggressive;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Scanning Docker build cache");
        var docker = Proc.Run(["docker", "system", "df"], 60_000);
        long cache = 0;
        if (docker.ExitCode == 0)
        {
            foreach (var line in docker.Stdout.Split('\n'))
            {
                if (!line.Contains("build cache", StringComparison.OrdinalIgnoreCase))
                    continue;
                foreach (var token in line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).Reverse())
                {
                    cache = ParseDocker(token);
                    if (cache > 0)
                        break;
                }
            }
        }
        if (cache > 0)
        {
            result.Items.Add(new CleanItem
            {
                Id = "docker_build_cache",
                Label = "Docker build cache",
                Detail = "docker builder prune (build cache only)",
                BytesEstimate = cache,
                DefaultInclude = false,
                Effect = "Runs docker builder prune to drop unused build cache.",
                Repercussions = "Build cache is removed. Images and containers you did not include stay.",
            });
        }
        foreach (var disk in WslDisks())
        {
            var size = Sizes.PathSize(disk, 2_000_000);
            if (size <= 0)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"wsl:{disk}:{size}",
                Label = $"WSL virtual disk ({Path.GetFileName(Path.GetDirectoryName(disk))})",
                Detail = $"{disk} — distro is kept. Size now {Sizes.Format(size)}.",
                BytesEstimate = size,
                DefaultInclude = false,
                Effect = "Compacts this WSL ext4.vhdx. The distro is not deleted.",
                Repercussions = "The Linux distro stays. Compact can take a long time and needs the distro stopped.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var scanned = Scan(progress);
        var plans = scanned.Items.Select(i => new PathPlan { Id = i.Id, Label = i.Label, DefaultInclude = i.DefaultInclude }).ToList();
        var allowed = PathRows.Select(plans, onlyIds, includeUnchecked).Select(p => p.Id).ToHashSet();
        scanned.Items.RemoveAll(i => !allowed.Contains(i.Id));
        scanned.DryRun = dryRun;
        foreach (var item in scanned.Items)
        {
            if (dryRun)
            {
                scanned.Actions.Add($"Would clean {item.Label}");
                scanned.BytesFreed += item.BytesEstimate;
                continue;
            }
            if (item.Id == "docker_build_cache")
            {
                var proc = Proc.Run(["docker", "builder", "prune", "-af"], 30 * 60 * 1000);
                if (proc.ExitCode == 0)
                {
                    scanned.Actions.Add("Pruned Docker build cache");
                    scanned.BytesFreed += item.BytesEstimate;
                }
                else
                {
                    item.Detail = proc.Tail;
                    scanned.Errors.Add($"{item.Id}: {proc.Tail}");
                }
                continue;
            }
            var body = item.Id[4..];
            var split = body.LastIndexOf(':');
            if (split <= 0)
            {
                scanned.Errors.Add($"{item.Id}: missing disk path");
                continue;
            }
            var disk = body[..split];
            progress?.Invoke("Stopping WSL so the virtual disk can compact...");
            Proc.Run(["wsl", "--shutdown"], 120_000);
            var scriptPath = Path.Combine(Path.GetTempPath(), $"wc-compact-{Guid.NewGuid():N}.txt");
            File.WriteAllText(scriptPath, $"select vdisk file=\"{disk}\"\r\nattach vdisk readonly\r\ncompact vdisk\r\ndetach vdisk\r\nexit\r\n");
            ProcessResult procDisk;
            try { procDisk = Proc.Run(["diskpart", "/s", scriptPath], 60 * 60 * 1000); }
            finally { try { File.Delete(scriptPath); } catch { } }
            if (procDisk.ExitCode == 0 && !procDisk.Stdout.Contains("encountered an error", StringComparison.OrdinalIgnoreCase))
            {
                scanned.Actions.Add($"Compacted {Path.GetFileName(disk)}; distro kept");
                scanned.BytesFreed += item.BytesEstimate;
            }
            else
            {
                item.Detail = procDisk.Tail.Length > 500 ? procDisk.Tail[..500] : procDisk.Tail;
                scanned.Errors.Add($"{item.Id}: {item.Detail}");
            }
        }
        return scanned;
    }

    private static List<string> WslDisks()
    {
        var local = Paths.Local();
        var found = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        void Add(string path)
        {
            if (!path.EndsWith("ext4.vhdx", StringComparison.OrdinalIgnoreCase) || !seen.Add(path) || !File.Exists(path))
                return;
            found.Add(path);
        }
        var root = Path.Combine(local, "wsl");
        if (Directory.Exists(root))
        {
            foreach (var distro in Directory.EnumerateDirectories(root))
            {
                Add(Path.Combine(distro, "ext4.vhdx"));
                foreach (var nested in Directory.EnumerateDirectories(distro))
                    Add(Path.Combine(nested, "ext4.vhdx"));
            }
        }
        var packages = Path.Combine(local, "Packages");
        if (Directory.Exists(packages))
        {
            foreach (var dir in Directory.EnumerateDirectories(packages))
                Add(Path.Combine(dir, "LocalState", "ext4.vhdx"));
        }
        return found;
    }

    private static long ParseDocker(string token)
    {
        token = token.Trim().ToUpperInvariant().Replace("IB", "B");
        try
        {
            if (token.EndsWith("GB")) return (long)(double.Parse(token[..^2], CultureInfo.InvariantCulture) * 1024 * 1024 * 1024);
            if (token.EndsWith("MB")) return (long)(double.Parse(token[..^2], CultureInfo.InvariantCulture) * 1024 * 1024);
            if (token.EndsWith("KB")) return (long)(double.Parse(token[..^2], CultureInfo.InvariantCulture) * 1024);
            if (token.EndsWith('B') && double.TryParse(token[..^1], NumberStyles.Float, CultureInfo.InvariantCulture, out var bytes))
                return (long)bytes;
        }
        catch (FormatException) { }
        return 0;
    }
}
