namespace WindowsCleaner;

public static class BrowserPaths
{
    private static readonly string[] CacheNames = ["Cache", "Code Cache", "GPUCache", "GraphiteDawnCache", "DawnGraphiteCache", "DawnWebGPUCache", "cache2"];
    private static readonly HashSet<string> Never = new(StringComparer.OrdinalIgnoreCase) { "cookies", "history", "login data", "web data", "bookmarks", "preferences" };
    private static readonly string[] PrivacyFiles = ["Cookies", "Cookies-journal", "History", "History-journal", "Visited Links", "Top Sites", "Top Sites-journal", "Web Data", "Web Data-journal", "Favicons", "Favicons-journal"];

    public static bool IsProfile(string path)
    {
        var name = Path.GetFileName(path);
        return name == "Default" || name.StartsWith("Profile ", StringComparison.Ordinal) || name == "Guest Profile";
    }

    public static List<string> CacheDirs(string profile)
    {
        var found = new List<string>();
        if (!Directory.Exists(profile))
            return found;
        Dictionary<string, string> present;
        try { present = Directory.EnumerateDirectories(profile).ToDictionary(p => Path.GetFileName(p) ?? "", p => p, StringComparer.OrdinalIgnoreCase); }
        catch { return found; }
        foreach (var name in CacheNames)
        {
            if (!present.TryGetValue(name, out var hit) || Never.Contains(Path.GetFileName(hit)))
                continue;
            found.Add(hit);
        }
        return found;
    }

    public static List<string> ChromiumCaches(string userData)
    {
        var found = new List<string>();
        if (!Directory.Exists(userData))
            return found;
        try
        {
            foreach (var profile in Directory.EnumerateDirectories(userData).Where(IsProfile))
                found.AddRange(CacheDirs(profile));
        }
        catch { }
        return found;
    }

    public static List<string> FirefoxCaches(string profiles)
    {
        var found = new List<string>();
        if (!Directory.Exists(profiles))
            return found;
        try
        {
            foreach (var profile in Directory.EnumerateDirectories(profiles))
            {
                var cache2 = Path.Combine(profile, "cache2");
                if (Directory.Exists(cache2))
                    found.Add(cache2);
            }
        }
        catch { }
        return found;
    }

    public static List<string> FilesNamed(string folder, IEnumerable<string> names)
    {
        var found = new List<string>();
        if (!Directory.Exists(folder))
            return found;
        Dictionary<string, string> present;
        try { present = Directory.EnumerateFiles(folder).ToDictionary(p => Path.GetFileName(p)!, p => p, StringComparer.OrdinalIgnoreCase); }
        catch { return found; }
        foreach (var name in names)
        {
            if (present.TryGetValue(name, out var hit))
                found.Add(hit);
        }
        return found;
    }

    public static List<string> ChromiumPrivacy(string userData)
    {
        var found = new List<string>();
        if (!Directory.Exists(userData))
            return found;
        try
        {
            foreach (var profile in Directory.EnumerateDirectories(userData).Where(IsProfile))
            {
                found.AddRange(FilesNamed(profile, PrivacyFiles));
                found.AddRange(FilesNamed(Path.Combine(profile, "Network"), ["Cookies", "Cookies-journal"]));
            }
        }
        catch { }
        return found;
    }

    public static List<string> FirefoxPrivacy(string profiles)
    {
        var found = new List<string>();
        if (!Directory.Exists(profiles))
            return found;
        try
        {
            foreach (var profile in Directory.EnumerateDirectories(profiles))
            {
                foreach (var name in new[] { "cookies.sqlite", "cookies.sqlite-wal", "places.sqlite", "places.sqlite-wal" })
                {
                    var path = Path.Combine(profile, name);
                    if (File.Exists(path))
                        found.Add(path);
                }
            }
        }
        catch { }
        return found;
    }
}

public sealed class BrowserCachesModule : CleanModule
{
    public override string Id => "browser_caches";
    public override string Label => "Browser Caches";
    public override string Description => "Edge, Chrome, Brave, Opera, Vivaldi, and Firefox cache folders, including extra profiles. Does not delete cookies, history, bookmarks, or passwords.";
    private const string Effect = "Deletes browser cache files (images, scripts, compiled pages).";
    private const string Reper = "Sites may load slower once. Cookies, history, bookmarks, and passwords stay.";

    private static List<PathPlan> Plans()
    {
        var local = Paths.Local();
        var roaming = Paths.Roaming();
        (string Id, string Label, List<string> Paths)[] rows =
        [
            ("edge_cache", "Edge caches", BrowserPaths.ChromiumCaches(Path.Combine(local, "Microsoft", "Edge", "User Data"))),
            ("chrome_cache", "Chrome caches", BrowserPaths.ChromiumCaches(Path.Combine(local, "Google", "Chrome", "User Data"))),
            ("brave_cache", "Brave caches", BrowserPaths.ChromiumCaches(Path.Combine(local, "BraveSoftware", "Brave-Browser", "User Data"))),
            ("vivaldi_cache", "Vivaldi caches", BrowserPaths.ChromiumCaches(Path.Combine(local, "Vivaldi", "User Data"))),
            ("opera_cache", "Opera caches", BrowserPaths.CacheDirs(Path.Combine(roaming, "Opera Software", "Opera Stable"))),
            ("opera_gx_cache", "Opera GX caches", BrowserPaths.CacheDirs(Path.Combine(roaming, "Opera Software", "Opera GX Stable"))),
            ("firefox_cache", "Firefox caches", BrowserPaths.FirefoxCaches(Path.Combine(roaming, "Mozilla", "Firefox", "Profiles"))),
        ];
        return rows.Where(r => r.Paths.Count > 0).Select(r => new PathPlan { Id = r.Id, Label = r.Label, Paths = r.Paths, Effect = Effect, Repercussions = Reper }).ToList();
    }

    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, Plans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, Plans(), dryRun, progress, onlyIds, includeUnchecked);
}

public sealed class BrowserPrivacyModule : CleanModule
{
    public override string Id => "browser_privacy";
    public override string Label => "Browser Cookies & History";
    public override string Description => "Cookies and history for Edge, Chrome, Brave, Opera, Vivaldi, and Firefox. This logs you out of sites. Opt-in, and not part of Free disk.";
    public override Risk Risk => Risk.Moderate;
    public override bool DefaultEnabled => false;
    private const string Reper = "Logs you out of websites and clears browsing history. Bookmarks file is kept. Not part of Free disk.";

    private static List<PathPlan> Plans()
    {
        var local = Paths.Local();
        var roaming = Paths.Roaming();
        (string Id, string Label, List<string> Paths)[] rows =
        [
            ("edge_privacy", "Edge cookies and history", BrowserPaths.ChromiumPrivacy(Path.Combine(local, "Microsoft", "Edge", "User Data"))),
            ("chrome_privacy", "Chrome cookies and history", BrowserPaths.ChromiumPrivacy(Path.Combine(local, "Google", "Chrome", "User Data"))),
            ("brave_privacy", "Brave cookies and history", BrowserPaths.ChromiumPrivacy(Path.Combine(local, "BraveSoftware", "Brave-Browser", "User Data"))),
            ("vivaldi_privacy", "Vivaldi cookies and history", BrowserPaths.ChromiumPrivacy(Path.Combine(local, "Vivaldi", "User Data"))),
            ("opera_privacy", "Opera cookies and history", BrowserPaths.FilesNamed(Path.Combine(roaming, "Opera Software", "Opera Stable"), ["Cookies", "History", "Visited Links", "Top Sites", "Web Data", "Favicons"]).Concat(BrowserPaths.FilesNamed(Path.Combine(roaming, "Opera Software", "Opera Stable", "Network"), ["Cookies", "Cookies-journal"])).ToList()),
            ("firefox_privacy", "Firefox cookies and history", BrowserPaths.FirefoxPrivacy(Path.Combine(roaming, "Mozilla", "Firefox", "Profiles"))),
        ];
        return rows.Where(r => r.Paths.Count > 0).Select(r => new PathPlan
        {
            Id = r.Id, Label = r.Label, Paths = r.Paths,
            Effect = "Deletes cookies and browsing history for this browser.",
            Repercussions = Reper,
        }).ToList();
    }

    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, Plans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, Plans(), dryRun, progress, onlyIds, includeUnchecked);
}

public sealed class DevCachesModule : CleanModule
{
    public override string Id => "dev_caches";
    public override string Label => "Developer Caches";
    public override string Description => "npm, pip, NuGet HTTP cache, Gradle, Go build cache, Yarn, pnpm, and Cargo git checkouts. Does not delete project folders, node_modules, Cargo registry sources, or NuGet packages.";
    public override bool DefaultEnabled => false;
    private const string Effect = "Deletes a developer tool cache that the next build can recreate.";
    private const string Reper = "The next build or install re-downloads what it needs. Project folders, node_modules, Cargo registry sources, and NuGet packages stay.";

    private static bool Safe(string path)
    {
        var parts = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).Select(p => p.ToLowerInvariant()).ToHashSet();
        if (parts.Contains("node_modules") || parts.Contains("program files") || parts.Contains("program files (x86)"))
            return false;
        var name = Path.GetFileName(path).ToLowerInvariant();
        var parent = Path.GetFileName(Path.GetDirectoryName(path) ?? "").ToLowerInvariant();
        if (name == "registry" && parent == ".cargo")
            return false;
        if (name == "packages" && parts.Contains(".nuget"))
            return false;
        return true;
    }

    private static List<PathPlan> Plans()
    {
        var home = Paths.Home();
        var local = Paths.Local();
        var roaming = Paths.Roaming();
        (string Id, string Label, string Path)[] candidates =
        [
            ("npm_cache", "npm cache", Path.Combine(roaming, "npm-cache")),
            ("npm_cache_local", "npm cache (local)", Path.Combine(local, "npm-cache")),
            ("pip_cache", "pip cache", Path.Combine(local, "pip", "Cache")),
            ("nuget_http_cache", "NuGet HTTP cache", Path.Combine(local, "NuGet", "v3-cache")),
            ("nuget_http_cache_alt", "NuGet HTTP cache (alt)", Path.Combine(local, "NuGet", "Cache")),
            ("gradle_cache", "Gradle caches", Path.Combine(home, ".gradle", "caches")),
            ("go_build_cache", "Go build cache", Path.Combine(local, "go-build")),
            ("yarn_cache", "Yarn cache", Path.Combine(local, "Yarn", "Cache")),
            ("pnpm_store", "pnpm store", Path.Combine(local, "pnpm", "store")),
            ("pnpm_store_home", "pnpm store (home)", Path.Combine(home, ".pnpm-store")),
            ("cargo_git", "Cargo git checkouts", Path.Combine(home, ".cargo", "git")),
        ];
        return candidates.Where(c => Safe(c.Path) && Fs.Exists(c.Path))
            .Select(c => new PathPlan { Id = c.Id, Label = c.Label, Paths = [c.Path], Effect = Effect, Repercussions = Reper })
            .ToList();
    }

    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, Plans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, Plans(), dryRun, progress, onlyIds, includeUnchecked);
}

public sealed class LogsModule : CleanModule
{
    public override string Id => "logs";
    public override string Label => "Logs & Crash Dumps";
    public override string Description => "CBS/DISM/Windows Update logs, minidumps, MEMORY.DMP, Windows Error Reporting archives, and Diagnosis folder leftovers.";
    public override bool RequiresAdmin => true;

    private static List<(string Id, string Label, string Path, bool File)> Targets()
    {
        var windir = Paths.WindowsDir();
        var data = Paths.ProgramData();
        return
        [
            ("cbs_logs", "Component Based Servicing logs", Path.Combine(windir, "Logs", "CBS"), false),
            ("dism_logs", "DISM logs", Path.Combine(windir, "Logs", "DISM"), false),
            ("wu_logs", "Windows Update logs", Path.Combine(windir, "Logs", "WindowsUpdate"), false),
            ("panther", "Setup Panther logs", Path.Combine(windir, "Panther"), false),
            ("minidump", "Kernel minidumps", Path.Combine(windir, "Minidump"), false),
            ("memory_dmp", "Memory.dmp (full crash dump)", Path.Combine(windir, "MEMORY.DMP"), true),
            ("wer_programdata", "Windows Error Reporting (system)", Path.Combine(data, "Microsoft", "Windows", "WER"), false),
            ("diagtrack_etl", "Diagnostics / telemetry ETL leftovers", Path.Combine(data, "Microsoft", "Diagnosis"), false),
            ("inetpub_logs", "IIS logs (if present)", @"C:\inetpub\logs", false),
        ];
    }

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        foreach (var (id, label, path, _) in Targets())
        {
            progress?.Invoke($"Scanning {label}");
            var size = Sizes.PathSize(path);
            if (size > 0)
                result.Items.Add(new CleanItem { Id = id, Label = label, Detail = path, BytesEstimate = size, RequiresAdmin = true });
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
        var admin = Admin.IsAdmin();
        foreach (var (id, label, path, file) in Targets())
        {
            if (!ItemFilter.Allow(id, onlyIds) || !Fs.Exists(path))
                continue;
            var item = new CleanItem { Id = id, Label = label, Detail = path, RequiresAdmin = true };
            result.Items.Add(item);
            if (!admin)
            {
                item.Detail = "Needs Administrator - not cleaned (will show again on Scan)";
                result.Errors.Add($"{id}: needs Administrator");
                continue;
            }
            progress?.Invoke($"Cleaning {label}");
            parts.Add(file ? Fs.DeletePath(path, false) : Fs.ClearDirectory(path, false));
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
