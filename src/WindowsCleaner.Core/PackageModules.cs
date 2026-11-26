using System.Text.Json;
using System.Text.RegularExpressions;

namespace WindowsCleaner;

public static class PackageMatch
{
    public static bool Matches(string haystack, string pattern)
    {
        var hay = haystack.ToLowerInvariant();
        var needle = pattern.ToLowerInvariant();
        if (needle.Contains('*'))
            return needle.Split('*', StringSplitOptions.RemoveEmptyEntries).All(hay.Contains);
        return hay.Contains(needle.Replace("*", ""));
    }

    public static List<JsonElement> ParseList(string raw)
    {
        raw = (raw ?? "").Trim();
        if (raw.Length == 0)
            return [];
        try
        {
            using var doc = JsonDocument.Parse(raw);
            if (doc.RootElement.ValueKind == JsonValueKind.Object)
                return [doc.RootElement.Clone()];
            if (doc.RootElement.ValueKind == JsonValueKind.Array)
                return doc.RootElement.EnumerateArray().Select(e => e.Clone()).ToList();
        }
        catch (JsonException) { }
        return [];
    }

    public static string Field(JsonElement pkg, params string[] names)
    {
        foreach (var name in names)
        {
            if (pkg.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String)
                return value.GetString() ?? "";
        }
        return "";
    }
}

public sealed class BloatwareModule : CleanModule
{
    public override string Id => "bloatware";
    public override string Label => "Preinstalled Bloatware";
    public override string Description => "Removes common Store and OEM junk and deprovisions matched packages so new users do not get them. Does not touch Store, Photos, Calculator, or Defender.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    private static List<JsonElement> Installed()
    {
        var scripts = new List<string> { "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress" };
        if (Admin.IsAdmin())
            scripts.Insert(0, "Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress");
        foreach (var script in scripts)
        {
            var proc = Proc.PowerShell(script, 120_000);
            if (proc.ExitCode != 0)
                continue;
            var pkgs = PackageMatch.ParseList(proc.Stdout);
            if (pkgs.Count > 0)
                return pkgs;
        }
        return [];
    }

    private static List<JsonElement> Provisioned()
    {
        var proc = Proc.PowerShell("Get-AppxProvisionedPackage -Online | Select-Object DisplayName, PackageName, PackageFamilyName | ConvertTo-Json -Compress", 120_000);
        return proc.ExitCode == 0 ? PackageMatch.ParseList(proc.Stdout) : [];
    }

    private static NameReason? Match(JsonElement pkg)
    {
        var hay = $"{PackageMatch.Field(pkg, "Name", "DisplayName")}|{PackageMatch.Field(pkg, "PackageFamilyName")}|{PackageMatch.Field(pkg, "PackageFullName", "PackageName")}";
        return Catalogs.Bloat.FirstOrDefault(b => PackageMatch.Matches(hay, b.Match));
    }

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Enumerating installed AppX packages...");
        var seenInstalled = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pkg in Installed())
        {
            var full = PackageMatch.Field(pkg, "PackageFullName");
            if (full.Length == 0 || !seenInstalled.Add(full))
                continue;
            var bloat = Match(pkg);
            if (bloat is null)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"installed:{full}",
                Label = bloat.Label,
                Detail = $"Installed — {PackageMatch.Field(pkg, "Name")} — {bloat.Reason}",
                RequiresAdmin = true,
                Effect = $"Uninstalls installed AppX: {bloat.Label}.",
                Repercussions = "Removed until reinstalled from the Microsoft Store. App data for it is lost.",
            });
        }
        progress?.Invoke("Enumerating provisioned AppX packages...");
        var seenProv = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pkg in Provisioned())
        {
            var name = PackageMatch.Field(pkg, "PackageName");
            if (name.Length == 0 || !seenProv.Add(name))
                continue;
            var bloat = Match(pkg);
            if (bloat is null)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"provisioned:{name}",
                Label = $"{bloat.Label} (provisioned)",
                Detail = $"Provisioned — {PackageMatch.Field(pkg, "DisplayName")} — {bloat.Reason}. Stays for new users until deprovisioned.",
                RequiresAdmin = true,
                Effect = $"Deprovisions AppX so new users do not get: {bloat.Label}.",
                Repercussions = "Stops reappearing for new users. Already-installed copies still need the Installed row removed.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
        result.DryRun = dryRun;
        var admin = Admin.IsAdmin();
        foreach (var item in result.Items)
        {
            progress?.Invoke($"{(dryRun ? "Would remove" : "Removing")} {item.Label}");
            if (dryRun)
            {
                result.Actions.Add($"Would remove {item.Id}");
                continue;
            }
            if (!admin)
            {
                item.Detail = "Needs Administrator - not removed (will show again on Scan)";
                item.Repercussions = "Run Restart as Administrator, then Clean again.";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            var value = item.Id.Split(':', 2)[1].Replace("'", "''");
            string script;
            if (item.Id.StartsWith("provisioned:"))
            {
                script = $"$p = Get-AppxProvisionedPackage -Online | Where-Object {{ $_.PackageName -eq '{value}' }}; if ($p) {{ $p | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue }}; 'DONE'";
            }
            else
            {
                script = $"Get-AppxPackage -AllUsers | Where-Object {{ $_.PackageFullName -eq '{value}' }} | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue; Get-AppxPackage | Where-Object {{ $_.PackageFullName -eq '{value}' }} | Remove-AppxPackage -ErrorAction SilentlyContinue; 'DONE'";
            }
            var proc = Proc.PowerShell(script, 180_000);
            if (proc.ExitCode == 0)
                result.Actions.Add(item.Id.StartsWith("provisioned:") ? $"Deprovisioned {item.Label}" : $"Removed {item.Label}");
            else
                result.Errors.Add($"{item.Label}: {proc.Tail}");
        }
        return result;
    }
}

public sealed class BloatwareOemModule : CleanModule
{
    public override string Id => "bloatware_oem";
    public override string Label => "OEM / Win32 Bloat";
    public override string Description => "HP, Dell, and Lenovo AppX families plus winget uninstall for SupportAssist, Vantage, Wolf, and AV trials.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Scanning OEM AppX packages...");
        var script = Admin.IsAdmin()
            ? "Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress"
            : "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName | ConvertTo-Json -Compress";
        var proc = Proc.PowerShell(script, 120_000);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pkg in PackageMatch.ParseList(proc.Stdout))
        {
            var full = PackageMatch.Field(pkg, "PackageFullName");
            var hay = $"{PackageMatch.Field(pkg, "Name")}|{PackageMatch.Field(pkg, "PackageFamilyName")}|{full}";
            var hit = Catalogs.OemAppx.FirstOrDefault(p => PackageMatch.Matches(hay, p.Match));
            if (hit is null || full.Length == 0 || !seen.Add(full))
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"appx:{full}",
                Label = hit.Label,
                Detail = $"AppX — {PackageMatch.Field(pkg, "Name")} — {hit.Reason}",
                RequiresAdmin = true,
                Effect = $"Uninstalls OEM AppX: {hit.Label}.",
                Repercussions = "OEM Store package removed; may return via drivers or BIOS.",
            });
        }
        progress?.Invoke("Scanning winget installed packages...");
        var winget = Proc.Run(["where", "winget"], 10_000);
        if (winget.ExitCode != 0)
        {
            result.Errors.Add("winget not found — Win32 OEM scan skipped");
            return result;
        }
        var list = Proc.Run(["winget", "list", "--accept-source-agreements"], 120_000);
        var seenWinget = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in list.Stdout.Split('\n'))
        {
            var parts = Regex.Split(line.Trim(), @"\s{2,}").Where(p => p.Length > 0).ToArray();
            if (parts.Length < 2)
                continue;
            var name = parts[0];
            var id = parts[1];
            if (id.Contains(' ') || name.Equals("Name", StringComparison.OrdinalIgnoreCase))
                continue;
            var target = Catalogs.WingetTargets.FirstOrDefault(t =>
                id.Contains(t.Match, StringComparison.OrdinalIgnoreCase) || name.Contains(t.Match, StringComparison.OrdinalIgnoreCase));
            if (target is null || !seenWinget.Add(id))
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"winget:{id}",
                Label = target.Label,
                Detail = $"winget — {name} ({id}) — {target.Reason}",
                RequiresAdmin = true,
                Effect = $"Uninstalls via winget: {target.Label}.",
                Repercussions = "Aggressive. Prefer the vendor removal tool for full AV suites. OEM tools may reinstall.",
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = Scan(progress);
        result.Items.RemoveAll(i => !ItemFilter.Allow(i.Id, onlyIds));
        result.DryRun = dryRun;
        var admin = Admin.IsAdmin();
        foreach (var item in result.Items.ToList())
        {
            if (dryRun)
            {
                result.Actions.Add($"Would remove {item.Label}");
                continue;
            }
            if (!admin)
            {
                item.Detail = "Needs Administrator - not removed (will show again on Scan)";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            if (item.Id.StartsWith("winget:"))
            {
                var id = item.Id.Split(':', 2)[1];
                var proc = Proc.Run(["winget", "uninstall", "--id", id, "--exact", "--accept-source-agreements", "--disable-interactivity"], 180_000);
                if (proc.ExitCode == 0)
                    result.Actions.Add($"Uninstalled via winget: {item.Label} ({id})");
                else
                    result.Errors.Add($"{item.Id}: {proc.Tail}");
            }
            else if (item.Id.StartsWith("appx:"))
            {
                var full = item.Id.Split(':', 2)[1].Replace("'", "''");
                var script = $"Get-AppxPackage -AllUsers | Where-Object {{ $_.PackageFullName -eq '{full}' }} | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue; Get-AppxPackage | Where-Object {{ $_.PackageFullName -eq '{full}' }} | Remove-AppxPackage -ErrorAction SilentlyContinue; 'DONE'";
                var proc = Proc.PowerShell(script, 180_000);
                if (proc.ExitCode == 0)
                    result.Actions.Add($"Removed {item.Label}");
                else
                    result.Errors.Add($"{item.Id}: {proc.Tail}");
            }
        }
        return result;
    }
}
