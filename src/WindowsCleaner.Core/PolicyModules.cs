using Microsoft.Win32;

namespace WindowsCleaner;

public sealed class PrivacyModule : CleanModule
{
    public override string Id => "privacy";
    public override string Label => "Privacy & Telemetry Hardening";
    public override string Description => "Applies registry and policy keys: telemetry, ads, Copilot/Recall, Widgets, Delivery Optimization, Edge, Find My Device, and suggestion switches. Does not uninstall Windows components or touch Defender.";
    public override Risk Risk => Risk.Moderate;
    public override bool RequiresAdmin => true;

    private static bool NeedsAdmin(PrivacySetting setting) =>
        setting.Hive == "HKLM" || setting.Path.Replace('/', '\\').Contains("\\Policies\\", StringComparison.Ordinal);

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        foreach (var setting in Catalogs.Privacy)
        {
            progress?.Invoke($"Checking {setting.Label}");
            var current = RegistryStore.GetValue(setting.Hive, setting.Path, setting.Name);
            if (RegistryStore.ValuesMatch(current, setting.Desired))
                continue;
            result.Items.Add(new CleanItem
            {
                Id = setting.Id,
                Label = setting.Label,
                Detail = $"{setting.Hive}\\{setting.Path}\\{setting.Name} = {current ?? "missing"} -> {setting.Desired}{WindowsInfo.TelemetryNote(setting.Id)}",
                RequiresAdmin = NeedsAdmin(setting),
                Effect = setting.Description,
            });
        }
        return result;
    }

    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label, DryRun = dryRun };
        var admin = Admin.IsAdmin();
        foreach (var setting in Catalogs.Privacy)
        {
            if (!ItemFilter.Allow(setting.Id, onlyIds))
                continue;
            var current = RegistryStore.GetValue(setting.Hive, setting.Path, setting.Name);
            if (RegistryStore.ValuesMatch(current, setting.Desired))
                continue;
            var needs = NeedsAdmin(setting);
            if (needs && !admin && !dryRun)
            {
                result.Items.Add(new CleanItem
                {
                    Id = setting.Id,
                    Label = setting.Label,
                    Detail = "Needs Administrator - not applied (will show again on Scan)",
                    RequiresAdmin = true,
                    Effect = setting.Description,
                    Repercussions = "Run Restart as Administrator, then Clean again.",
                });
                result.Errors.Add($"{setting.Id}: needs Administrator (write denied without elevation)");
                continue;
            }
            progress?.Invoke($"{(dryRun ? "Would set" : "Setting")} {setting.Label}");
            var change = RegistryStore.SetDword(setting.Hive, setting.Path, setting.Name, setting.Desired, dryRun);
            result.Items.Add(new CleanItem
            {
                Id = setting.Id,
                Label = setting.Label,
                Detail = change.Ok ? setting.Description : change.Error ?? "write failed",
                RequiresAdmin = needs,
                Effect = setting.Description,
                Repercussions = change.Ok && !dryRun
                    ? "Applied."
                    : "Will keep appearing on Scan until write succeeds (usually needs Admin).",
            });
            if (change.Ok)
            {
                result.Actions.Add($"{(dryRun ? "Would set" : "Set")} {setting.Hive}\\{setting.Path}\\{setting.Name}={setting.Desired} (was {current ?? "missing"})");
                if (!dryRun)
                    PrivacyUndo.Record(setting.Id, setting.Label, setting.Hive, setting.Path, setting.Name, current, setting.Desired);
            }
            else
                result.Errors.Add($"{setting.Id}: {change.Error ?? "failed to write registry value"}");
        }
        return result;
    }
}

public sealed class TelemetryServicesModule : CleanModule
{
    public override string Id => "telemetry_services";
    public override string Label => "Telemetry Services & Tasks";
    public override string Description => "Disables DiagTrack and related services, plus CEIP / Compatibility / Feedback scheduled tasks. Reversible via services.msc and Task Scheduler.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Reading service states");
        var states = ServiceControl.QueryStates("service");
        foreach (var svc in Catalogs.TelemetryServices)
        {
            var start = ServiceControl.StartFromRegistry(svc.Name);
            if (start is null || start.Contains("DISABLED", StringComparison.OrdinalIgnoreCase))
                continue;
            states.TryGetValue(svc.Name, out var state);
            result.Items.Add(new CleanItem
            {
                Id = $"svc:{svc.Name}",
                Label = $"Service: {svc.Label}",
                Detail = $"{svc.Name} - {svc.Reason} (current: {start}; {state})",
                RequiresAdmin = true,
            });
        }
        progress?.Invoke("Reading scheduled tasks");
        var tasks = ServiceControl.QueryScheduledTasks();
        foreach (var task in Catalogs.TelemetryTasks)
        {
            if (!tasks.TryGetValue(task.Path, out var enabled) || !enabled)
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"task:{task.Path}",
                Label = $"Task: {task.Label}",
                Detail = $"{task.Path} - {task.Reason}",
                RequiresAdmin = true,
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
            progress?.Invoke($"{(dryRun ? "Would disable" : "Disabling")} {item.Label}");
            if (!dryRun && !admin)
            {
                item.Detail = "Needs Administrator - not applied (will show again on Scan)";
                item.Repercussions = "Run Restart as Administrator, then Clean again.";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            if (item.Id.StartsWith("svc:", StringComparison.Ordinal))
            {
                var name = item.Id.Split(':', 2)[1];
                if (dryRun)
                {
                    result.Actions.Add($"Would disable service {name}");
                    continue;
                }
                Proc.Run(["sc", "stop", name], 20_000);
                var (start, _) = ServiceControl.State(name);
                ChangeUndo.RememberService(name, start);
                var cfg = Proc.Run(["sc", "config", name, "start=", "disabled"]);
                if (cfg.ExitCode == 0)
                    result.Actions.Add($"Disabled service {name}");
                else
                {
                    item.Detail = cfg.Tail;
                    result.Errors.Add($"{item.Id}: {cfg.Tail}");
                }
            }
            else if (item.Id.StartsWith("task:", StringComparison.Ordinal))
            {
                var path = item.Id.Split(':', 2)[1];
                if (dryRun)
                {
                    result.Actions.Add($"Would disable task {path}");
                    continue;
                }
                var proc = Proc.Run(["schtasks", "/Change", "/TN", path, "/Disable"]);
                if (proc.ExitCode == 0)
                    result.Actions.Add($"Disabled task {path}");
                else
                {
                    item.Detail = proc.Tail;
                    result.Errors.Add($"{item.Id}: {proc.Tail}");
                }
            }
        }
        return result;
    }
}

public sealed class PerfServicesModule : CleanModule
{
    public override string Id => "perf_services";
    public override string Label => "Optional Performance Services";
    public override string Description => "Optionally disables SysMain (Superfetch) and/or Windows Search indexer. Helps some PCs, hurts others. Never on in Safe, Standard, or Privacy.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        var states = ServiceControl.QueryStates("service");
        foreach (var svc in Catalogs.PerfServices)
        {
            var start = ServiceControl.StartFromRegistry(svc.Name);
            states.TryGetValue(svc.Name, out var state);
            if (start is null || start.Contains("DISABLED", StringComparison.OrdinalIgnoreCase))
                continue;
            result.Items.Add(new CleanItem
            {
                Id = $"svc:{svc.Name}",
                Label = $"Service: {svc.Label}",
                Detail = $"{svc.Name} — {svc.Reason} (current: {start}; {state})",
                RequiresAdmin = true,
                Effect = $"Sets {svc.Name} startup type to Disabled and stops it if running.",
                Repercussions = svc.Reason + " Re-enable anytime in services.msc.",
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
            if (!dryRun && !admin)
            {
                item.Detail = "Needs Administrator - not applied (will show again on Scan)";
                item.Repercussions = "Run Restart as Administrator, then Clean again.";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            var name = item.Id.Split(':', 2)[1];
            if (dryRun)
            {
                result.Actions.Add($"Would disable service {name}");
                continue;
            }
            Proc.Run(["sc", "stop", name], 20_000);
            var (start, _) = ServiceControl.State(name);
            ChangeUndo.RememberService(name, start);
            var cfg = Proc.Run(["sc", "config", name, "start=", "disabled"]);
            if (cfg.ExitCode == 0)
                result.Actions.Add($"Disabled service {name}");
            else
            {
                item.Detail = cfg.Tail;
                result.Errors.Add($"{item.Id}: {cfg.Tail}");
            }
        }
        return result;
    }
}

public sealed class StartupServicesModule : CleanModule
{
    public override string Id => "startup_services";
    public override string Label => "Optional Startup Services";
    public override string Description => "Stops Windows services that are not required on a typical PC (Fax, Xbox, print spooler, Remote Desktop listener, Phone Link). Does not touch Defender, Windows Update, firewall, audio, Wi-Fi, Bluetooth, or Windows Hello.";
    public override Risk Risk => Risk.Aggressive;
    public override bool RequiresAdmin => true;
    public override bool DefaultEnabled => false;

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Reading startup service states");
        var states = ServiceControl.QueryStates("service");
        var userStates = ServiceControl.QueryStates("userservice");
        foreach (var svc in Catalogs.StartupServices)
        {
            string current;
            if (svc.PerUser)
            {
                var rows = UserInstances(svc.Name, userStates).Where(r => ServiceControl.ShouldOffer(r.Start, r.State, svc.Target)).ToList();
                if (rows.Count == 0)
                {
                    var start = ServiceControl.StartFromRegistry(svc.Name);
                    states.TryGetValue(svc.Name, out var state);
                    if (ServiceControl.ShouldOffer(start, state, svc.Target))
                        rows.Add((svc.Name, start, state));
                }
                if (rows.Count == 0)
                    continue;
                current = string.Join("; ", rows.Take(2).Select(r => $"{r.Name}: {r.Start ?? "?"} / {r.State ?? "?"}"));
                if (rows.Count > 2)
                    current += $" (+{rows.Count - 2} more)";
            }
            else
            {
                var start = ServiceControl.StartFromRegistry(svc.Name);
                states.TryGetValue(svc.Name, out var state);
                if (!ServiceControl.ShouldOffer(start, state, svc.Target))
                    continue;
                current = $"{start}; {state}";
            }
            var disabled = svc.Target == "disabled";
            result.Items.Add(new CleanItem
            {
                Id = $"{(svc.PerUser ? "usvc" : "svc")}:{svc.Name}",
                Label = $"Service: {svc.Label}",
                Detail = $"{svc.Name} — {svc.Reason} (current: {current})",
                RequiresAdmin = true,
                Effect = disabled
                    ? $"Sets {svc.Label} to Disabled and stops it."
                    : $"Sets {svc.Label} to Manual and stops it now so it is not resident after boot.",
                Repercussions = (disabled
                    ? "Disabled — it will not start until you turn it back on. "
                    : "Manual — Windows can still start it when a feature asks. ") + $"Keep this service if: {svc.KeepIf} Re-enable in services.msc.",
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
        var byName = Catalogs.StartupServices.ToDictionary(s => s.Name, StringComparer.OrdinalIgnoreCase);
        var userStates = ServiceControl.QueryStates("userservice");
        foreach (var item in result.Items)
        {
            if (!dryRun && !admin)
            {
                item.Detail = "Needs Administrator - not applied (will show again on Scan)";
                item.Repercussions = "Run Restart as Administrator, then Clean again.";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            var name = item.Id.Split(':', 2)[1];
            if (!byName.TryGetValue(name, out var svc))
            {
                result.Errors.Add($"{item.Id}: unknown service");
                continue;
            }
            var verb = svc.Target == "disabled" ? "disable" : "set to Manual";
            var names = new List<string> { name };
            if (svc.PerUser)
            {
                names = UserInstances(name, userStates).Select(r => r.Name).ToList();
                if (!names.Contains(name, StringComparer.OrdinalIgnoreCase))
                    names.Insert(0, name);
            }
            if (dryRun)
            {
                result.Actions.Add($"Would {verb} {string.Join(", ", names)}");
                continue;
            }
            var ok = 0;
            var failures = new List<string>();
            foreach (var target in names)
            {
                var (start, _) = ServiceControl.State(target);
                ChangeUndo.RememberService(target, start);
                var mode = svc.Target == "disabled" ? "disabled" : "demand";
                Proc.Run(["sc", "stop", target], 20_000);
                var cfg = Proc.Run(["sc", "config", target, "start=", mode]);
                if (cfg.ExitCode == 0)
                    ok++;
                else if (cfg.ExitCode != 1060)
                    failures.Add($"{target}: {cfg.Tail}");
            }
            if (ok > 0 && failures.Count == 0)
                result.Actions.Add($"{char.ToUpper(verb[0])}{verb[1..]} {name}");
            else if (ok > 0)
            {
                result.Actions.Add($"{char.ToUpper(verb[0])}{verb[1..]} {name} (partial)");
                result.Errors.Add($"{item.Id}: {string.Join("; ", failures)}");
            }
            else
            {
                var err = failures.Count == 0 ? "service was not changed" : string.Join("; ", failures);
                item.Detail = err;
                result.Errors.Add($"{item.Id}: {err}");
            }
        }
        return result;
    }

    private static List<(string Name, string? Start, string? State)> UserInstances(string prefix, Dictionary<string, string> userStates)
    {
        var found = new List<(string, string?, string?)>();
        foreach (var (name, state) in userStates)
        {
            if (name.Equals(prefix, StringComparison.OrdinalIgnoreCase) || name.StartsWith(prefix + "_", StringComparison.OrdinalIgnoreCase))
                found.Add((name, ServiceControl.StartFromRegistry(name), state));
        }
        return found;
    }
}

public sealed class StartupAppsModule : CleanModule
{
    public override string Id => "startup_apps";
    public override string Label => "Startup Programs";
    public override string Description => "Lists HKCU/HKLM Run entries and Startup-folder shortcuts. Clean removes the selected entry. Does not touch services or Task Scheduler.";
    public override Risk Risk => Risk.Moderate;
    public override bool DefaultEnabled => false;
    private const string RunPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";

    public override ModuleResult Scan(Action<string>? progress)
    {
        var result = new ModuleResult { ModuleId = Id, Label = Label };
        progress?.Invoke("Scanning HKCU Run...");
        foreach (var (name, value, _) in RegistryStore.EnumerateValues("HKCU", RunPath))
        {
            result.Items.Add(new CleanItem
            {
                Id = $"hkcu_run:{name}",
                Label = $"HKCU Run: {name}",
                Detail = value,
                Effect = $"Removes user Run entry '{name}' so it no longer starts at logon.",
                Repercussions = "App will not auto-start for this user until re-added.",
            });
        }
        progress?.Invoke("Scanning HKLM Run...");
        foreach (var (name, value, _) in RegistryStore.EnumerateValues("HKLM", RunPath))
        {
            result.Items.Add(new CleanItem
            {
                Id = $"hklm_run:{name}",
                Label = $"HKLM Run: {name}",
                Detail = value,
                RequiresAdmin = true,
                Effect = $"Removes machine Run entry '{name}' (all users).",
                Repercussions = "Stops auto-start for all users until re-added. Needs Admin.",
            });
        }
        progress?.Invoke("Scanning Startup folder...");
        foreach (var folder in new[]
        {
            Path.Combine(Paths.Roaming(), @"Microsoft\Windows\Start Menu\Programs\Startup"),
            Path.Combine(Paths.ProgramData(), @"Microsoft\Windows\Start Menu\Programs\Startup"),
        })
        {
            if (!Directory.Exists(folder))
                continue;
            foreach (var file in Directory.EnumerateFiles(folder))
            {
                var ext = Path.GetExtension(file).ToLowerInvariant();
                if (ext is not (".lnk" or ".url" or ".bat" or ".cmd" or ".exe"))
                    continue;
                var common = file.Contains("ProgramData", StringComparison.OrdinalIgnoreCase);
                result.Items.Add(new CleanItem
                {
                    Id = $"startup_file:{file}",
                    Label = $"Startup folder: {Path.GetFileName(file)}",
                    Detail = file,
                    RequiresAdmin = common,
                    Effect = $"Deletes Startup shortcut/script: {Path.GetFileName(file)}.",
                    Repercussions = "File removed from Startup folder. Does not uninstall the application.",
                });
            }
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
            if (dryRun)
            {
                result.Actions.Add($"Would remove {item.Id}");
                continue;
            }
            if (item.RequiresAdmin && !admin)
            {
                item.Detail = "Needs Administrator - not removed (will show again on Scan)";
                item.Repercussions = "Run Restart as Administrator, then Clean again.";
                result.Errors.Add($"{item.Id}: needs Administrator");
                continue;
            }
            if (item.Id.StartsWith("hkcu_run:") || item.Id.StartsWith("hklm_run:"))
            {
                var hive = item.Id.StartsWith("hkcu_run:") ? "HKCU" : "HKLM";
                var name = item.Id.Split(':', 2)[1];
                var current = RegistryStore.EnumerateValues(hive, RunPath).FirstOrDefault(v => v.Name == name);
                if (!string.IsNullOrEmpty(current.Name))
                    ChangeUndo.RememberRun(hive, RunPath, name, current.Value, current.Kind);
                var (ok, err) = RegistryStore.DeleteValue(hive, RunPath, name);
                if (ok)
                    result.Actions.Add($"Removed {hive} Run: {name}");
                else
                    result.Errors.Add($"{item.Id}: {err ?? "failed"}");
            }
            else if (item.Id.StartsWith("startup_file:"))
            {
                var path = item.Id.Split(':', 2)[1];
                try
                {
                    if (File.Exists(path))
                        File.Delete(path);
                    result.Actions.Add($"Deleted {path}");
                }
                catch (Exception ex)
                {
                    result.Errors.Add($"{item.Id}: {ex.Message}");
                }
            }
        }
        return result;
    }
}
