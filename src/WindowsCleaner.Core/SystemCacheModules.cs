using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace WindowsCleaner;

public sealed class CachesModule : CleanModule
{
    public override string Id => "caches";
    public override string Label => "System & Update Caches";
    public override string Description => "Windows Update download cache, Delivery Optimization P2P cache, Explorer thumbnails, optional Prefetch, and Windows.old if present.";
    public override Risk Risk => Risk.Moderate;

    private static List<(string Id, string Label, string Path, bool Admin)> Targets()
    {
        var windir = Paths.WindowsDir();
        var local = Paths.Local();
        var data = Paths.ProgramData();
        return
        [
            ("wu_download", "Windows Update download cache", Path.Combine(windir, @"SoftwareDistribution\Download"), true),
            ("delivery_opt", "Delivery Optimization cache", Path.Combine(windir, "SoftwareDistribution", "DeliveryOptimization"), true),
            ("delivery_opt_alt", "Delivery Optimization files", @"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache", true),
            ("thumbcache", "Explorer thumbnail cache", Path.Combine(local, @"Microsoft\Windows\Explorer"), false),
            ("font_cache", "Font cache (service files)", Path.Combine(windir, "ServiceProfiles", "LocalService", "AppData", "Local", "FontCache"), true),
            ("prefetch", "Prefetch (rarely needed; may slow next cold boots briefly)", Path.Combine(windir, "Prefetch"), true),
            ("installer_cache_partial", "Windows Installer patch cache leftovers", Path.Combine(windir, "Installer", "$PatchCache$"), true),
            ("do_programdata", "Delivery Optimization ProgramData", Path.Combine(data, "Microsoft", "Windows", "DeliveryOptimization"), true),
            ("webcache", "Windows WebCache (Explorer/Edge leftovers)", Path.Combine(local, @"Microsoft\Windows\WebCache"), false),
            ("windows_old", "Windows.old (previous Windows installation — large, irreversible)", @"C:\Windows.old", true),
        ];
    }

    private static long ThumbSize(string path)
    {
        if (!Directory.Exists(path))
            return 0;
        long size = 0;
        foreach (var pattern in new[] { "thumbcache_*.db", "iconcache_*.db" })
        {
            foreach (var file in Directory.EnumerateFiles(path, pattern))
                size += Sizes.PathSize(file);
        }
        return size;
    }

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        foreach (var (id, label, path, admin) in Targets())
        {
            progress?.Invoke($"Scanning {label}");
            var size = id == "thumbcache" ? ThumbSize(path) : Sizes.PathSize(path);
            if (size <= 0)
                continue;
            result.Items.Add(new CleanItem { Id = id, Label = label, Detail = path, BytesEstimate = size, RequiresAdmin = admin });
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
        foreach (var (id, label, path, needs) in Targets())
        {
            if (!ItemFilter.Allow(id, onlyIds) || !Fs.Exists(path))
                continue;
            var item = new CleanItem { Id = id, Label = label, Detail = path, RequiresAdmin = needs };
            result.Items.Add(item);
            if (needs && !admin)
            {
                item.Detail = "Needs Administrator - not cleaned (will show again on Scan)";
                result.Errors.Add($"{id}: needs Administrator");
                continue;
            }
            progress?.Invoke($"Cleaning {label}");
            var before = parts.Count;
            if (id == "thumbcache")
            {
                Proc.Run(["taskkill", "/f", "/im", "explorer.exe"], 15_000);
                foreach (var pattern in new[] { "thumbcache_*.db", "iconcache_*.db" })
                {
                    foreach (var file in Directory.EnumerateFiles(path, pattern))
                        parts.Add(Fs.DeletePath(file, false));
                }
                Proc.Run(["explorer.exe"], 5_000);
            }
            else if (id == "prefetch")
            {
                foreach (var file in Directory.EnumerateFiles(path, "*.pf"))
                    parts.Add(Fs.DeletePath(file, false));
            }
            else if (id == "windows_old")
                parts.Add(Fs.DeletePath(path, false));
            else
                parts.Add(Fs.ClearDirectory(path, false));
            var errors = parts.Skip(before).SelectMany(p => p.Errors).ToList();
            if (errors.Count > 0)
                result.Errors.AddRange(errors);
            else
                result.Actions.Add($"Cleaned {label}");
        }
        if (parts.Count > 0)
        {
            var merged = Fs.Merge(parts);
            result.BytesFreed = merged.BytesFreed;
            foreach (var error in merged.Errors)
            {
                if (!result.Errors.Contains(error))
                    result.Errors.Add(error);
            }
        }
        return result;
    }
}

public sealed class TrackingModule : CleanModule
{
    public override string Id => "tracking";
    public override string Label => "Tracking & Activity Data";
    public override string Description => "Timeline/Activity History databases, Search/Cortana leftovers, notification and clipboard history, Content Delivery suggestion caches, and shared diagnostic staging folders.";
    public override Risk Risk => Risk.Moderate;

    private static List<(string Id, string Label, string Path)> Targets()
    {
        var local = Paths.Local();
        var data = Paths.ProgramData();
        return
        [
            ("activity_history", "Timeline / Activity History DB", Path.Combine(local, "ConnectedDevicesPlatform")),
            ("search_cortana", "Search / Cortana local state", Path.Combine(local, "Packages", "Microsoft.Windows.Search_cw5n1h2txyewy")),
            ("cortana_pkg", "Cortana package data", Path.Combine(local, "Packages", "Microsoft.549981C3F5F10_8wekyb3d8bbwe")),
            ("notifications", "Notification history", Path.Combine(local, "Microsoft", "Windows", "Notifications")),
            ("clipboard", "Clipboard history", Path.Combine(local, "Microsoft", "Windows", "Clipboard")),
            ("cdm", "Content Delivery Manager (Start suggestions)", Path.Combine(local, "Packages", "Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy")),
            ("onedrive_logs", "OneDrive logs", Path.Combine(local, "Microsoft", "OneDrive", "logs")),
            ("speech", "Speech services cache", Path.Combine(local, "Microsoft", "SpeechServices")),
            ("diag_programdata", "Shared diagnostics / telemetry stage", Path.Combine(data, "Microsoft", "Diagnosis")),
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
                result.Items.Add(new CleanItem { Id = id, Label = label, Detail = path, BytesEstimate = size, RequiresAdmin = id == "diag_programdata" });
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
        var clear = new HashSet<string> { "activity_history", "notifications", "clipboard", "onedrive_logs", "speech", "diag_programdata" };
        var packages = new HashSet<string> { "search_cortana", "cortana_pkg", "cdm" };
        foreach (var (id, label, path) in Targets())
        {
            if (!ItemFilter.Allow(id, onlyIds) || !Fs.Exists(path))
                continue;
            var needs = id == "diag_programdata";
            var item = new CleanItem { Id = id, Label = label, Detail = path, RequiresAdmin = needs };
            result.Items.Add(item);
            if (needs && !admin)
            {
                item.Detail = "Needs Administrator - not cleaned (will show again on Scan)";
                result.Errors.Add($"{id}: needs Administrator");
                continue;
            }
            progress?.Invoke($"Cleaning {label}");
            if (packages.Contains(id))
            {
                foreach (var sub in new[] { "LocalCache", "TempState", "AC" })
                {
                    var subpath = Path.Combine(path, sub);
                    if (Directory.Exists(subpath))
                        parts.Add(Fs.ClearDirectory(subpath, false));
                }
                var localState = Path.Combine(path, "LocalState");
                if (Directory.Exists(localState))
                {
                    foreach (var pattern in new[] { "*.db", "*.db-wal", "*.db-shm", "*.log", "*.etl" })
                    {
                        foreach (var file in Directory.EnumerateFiles(localState, pattern))
                            parts.Add(Fs.DeletePath(file, false));
                        foreach (var dir in Directory.EnumerateDirectories(localState))
                        {
                            foreach (var file in Directory.EnumerateFiles(dir, pattern))
                                parts.Add(Fs.DeletePath(file, false));
                        }
                    }
                }
            }
            else if (clear.Contains(id))
                parts.Add(Fs.ClearDirectory(path, false));
            else
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

public sealed class AppCachesModule : CleanModule
{
    public override string Id => "app_caches";
    public override string Label => "App Caches";
    public override string Description => "Discord, Slack, Zoom, Teams, Spotify, Steam shader cache, Epic and Battle.net web caches, and extracted NVIDIA/AMD/Intel driver folders at the drive root.";
    private const string Effect = "Deletes regenerating cache files for this app.";
    private const string Reper = "The app may load slower once. Login databases and the install stay. Quit the app first.";
    private static readonly string[] Electron = ["Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache", "logs", "Crashpad"];
    private static readonly HashSet<string> Login = new(StringComparer.OrdinalIgnoreCase) { "local storage", "indexeddb", "session storage", "local state", "cookies", "login data" };

    private static List<string> ChildrenNamed(string parent, IEnumerable<string> names)
    {
        if (!Directory.Exists(parent))
            return [];
        Dictionary<string, string> present;
        try { present = Directory.EnumerateFileSystemEntries(parent).ToDictionary(p => Path.GetFileName(p)!, p => p, StringComparer.OrdinalIgnoreCase); }
        catch { return []; }
        var found = new List<string>();
        foreach (var name in names)
        {
            if (present.TryGetValue(name, out var hit) && !Login.Contains(Path.GetFileName(hit)))
                found.Add(hit);
        }
        return found;
    }

    private static List<string> ElectronCaches(string root)
    {
        var found = ChildrenNamed(root, Electron);
        var localCache = Path.Combine(root, "LocalCache");
        found.AddRange(ChildrenNamed(localCache, Electron));
        if (!Directory.Exists(localCache))
            return found;
        try
        {
            foreach (var child in Directory.EnumerateDirectories(localCache))
            {
                found.AddRange(ChildrenNamed(child, Electron));
                found.AddRange(ChildrenNamed(Path.Combine(child, "Default"), Electron));
            }
        }
        catch { }
        return found;
    }

    private static List<string> PackageDirs(string prefix)
    {
        var packages = Path.Combine(Paths.Local(), "Packages");
        if (!Directory.Exists(packages))
            return [];
        try
        {
            return Directory.EnumerateDirectories(packages)
                .Where(d => Path.GetFileName(d).StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                .ToList();
        }
        catch { return []; }
    }

    private static List<string> SteamCaches()
    {
        var roots = new List<string>();
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
            var value = key?.GetValue("SteamPath")?.ToString();
            if (!string.IsNullOrEmpty(value))
                roots.Add(value);
        }
        catch { }
        roots.Add(@"C:\Program Files (x86)\Steam");
        roots.Add(@"C:\Program Files\Steam");
        var libraries = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var root in roots.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            var steamapps = Path.Combine(root, "steamapps");
            if (Directory.Exists(steamapps) && seen.Add(steamapps))
                libraries.Add(steamapps);
            var vdf = Path.Combine(steamapps, "libraryfolders.vdf");
            string text;
            try { text = File.ReadAllText(vdf); }
            catch { continue; }
            foreach (Match match in Regex.Matches(text, "\"([A-Za-z]:[^\"]+)\""))
            {
                var apps = Path.Combine(match.Groups[1].Value.Replace("\\\\", "\\"), "steamapps");
                if (seen.Add(apps))
                    libraries.Add(apps);
            }
        }
        var found = new List<string>();
        foreach (var steamapps in libraries)
        {
            foreach (var name in new[] { "shadercache", "downloading" })
            {
                var path = Path.Combine(steamapps, name);
                var parts = path.Split(Path.DirectorySeparatorChar).Select(p => p.ToLowerInvariant()).ToHashSet();
                if (Directory.Exists(path) && !parts.Contains("common"))
                    found.Add(path);
            }
        }
        return found;
    }

    private static List<string> DriveExtracts()
    {
        var root = Paths.SystemDrive() + "\\";
        var found = new List<string>();
        foreach (var name in new[] { "NVIDIA", "AMD", "Intel" })
        {
            var path = Path.Combine(root, name);
            var parts = path.Split(Path.DirectorySeparatorChar).Select(p => p.ToLowerInvariant()).ToHashSet();
            if (parts.Contains("program files") || parts.Contains("program files (x86)"))
                continue;
            if (Directory.Exists(path))
                found.Add(path);
        }
        return found;
    }

    private static List<PathPlan> Plans()
    {
        var roaming = Paths.Roaming();
        var local = Paths.Local();
        var rows = new List<PathPlan>();
        (string Id, string Label, string Root)[] apps =
        [
            ("discord_cache", "Discord caches", Path.Combine(roaming, "discord")),
            ("discord_canary_cache", "Discord Canary caches", Path.Combine(roaming, "discordcanary")),
            ("slack_cache", "Slack caches", Path.Combine(roaming, "Slack")),
            ("zoom_cache", "Zoom caches", Path.Combine(roaming, "Zoom")),
            ("teams_classic_cache", "Teams classic caches", Path.Combine(roaming, "Microsoft", "Teams")),
        ];
        foreach (var (id, label, root) in apps)
        {
            var paths = ElectronCaches(root);
            if (paths.Count > 0)
                rows.Add(new PathPlan { Id = id, Label = label, Paths = paths, Effect = Effect, Repercussions = Reper });
        }
        foreach (var folder in PackageDirs("MSTeams_"))
        {
            var paths = ElectronCaches(folder);
            if (paths.Count > 0)
            {
                rows.Add(new PathPlan { Id = "teams_cache", Label = "New Teams caches", Paths = paths, Effect = Effect, Repercussions = Reper });
                break;
            }
        }
        var spotify = ChildrenNamed(Path.Combine(local, "Spotify"), ["Storage"]);
        spotify.AddRange(ElectronCaches(Path.Combine(roaming, "Spotify")));
        foreach (var folder in PackageDirs("SpotifyAB.SpotifyMusic"))
            spotify.AddRange(ElectronCaches(folder));
        if (spotify.Count > 0)
            rows.Add(new PathPlan { Id = "spotify_cache", Label = "Spotify caches", Paths = spotify, Effect = Effect, Repercussions = Reper });
        var epic = Path.Combine(local, "EpicGamesLauncher", "Saved");
        if (Directory.Exists(epic))
        {
            var epicPaths = Directory.EnumerateDirectories(epic, "webcache*").ToList();
            if (epicPaths.Count > 0)
                rows.Add(new PathPlan { Id = "epic_cache", Label = "Epic Games web cache", Paths = epicPaths, Effect = Effect, Repercussions = "Launcher web cache only. Installed games stay." });
        }
        var bnet = ChildrenNamed(Path.Combine(local, "Battle.net"), ["Cache"]);
        bnet.AddRange(ChildrenNamed(Path.Combine(roaming, "Battle.net"), ["BrowserCache", "Cache"]));
        if (bnet.Count > 0)
            rows.Add(new PathPlan { Id = "battlenet_cache", Label = "Battle.net caches", Paths = bnet, Effect = Effect, Repercussions = "Launcher cache only. Installed games stay." });
        var steam = SteamCaches();
        if (steam.Count > 0)
            rows.Add(new PathPlan { Id = "steam_shader_cache", Label = "Steam shader cache and download staging", Paths = steam, Effect = "Deletes Steam shadercache and leftover download staging.", Repercussions = "Games in steamapps\\common and save games stay. Shaders rebuild later." });
        var extracts = DriveExtracts();
        if (extracts.Count > 0)
            rows.Add(new PathPlan { Id = "driver_extracts", Label = "Extracted driver setup folders", Paths = extracts, Effect = "Deletes NVIDIA, AMD, or Intel driver extracts at the drive root.", Repercussions = "Does not touch C:\\Program Files. The vendor installer can extract these again." });
        return rows;
    }

    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, Plans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, Plans(), dryRun, progress, onlyIds, includeUnchecked);
}
