using WindowsCleaner;

namespace WindowsCleaner.App;

public static class Cli
{
    public static int Run(string[] args)
    {
        var rest = args.Where(a => a != "--cli").ToList();
        var elevate = rest.Remove("--elevate");
        if (elevate && !Admin.IsAdmin())
        {
            Admin.RelaunchAsAdmin();
            return 0;
        }
        if (rest.Count == 0 || rest[0] is "help" or "--help" or "-h")
        {
            PrintHelp();
            return 0;
        }
        var command = rest[0];
        rest.RemoveAt(0);
        return command switch
        {
            "modules" => Modules(),
            "disclaimer" => Text(Disclaimer.Full),
            "scan" => Execute(rest, clean: false, dry: false),
            "clean" => Execute(rest, clean: true, dry: rest.Contains("--dry-run")),
            "undo-privacy" => Undo(PrivacyUndo.UndoAll(rest.Contains("--dry-run"))),
            "undo-startup" => Undo(ChangeUndo.UndoAll(rest.Contains("--dry-run"))),
            _ => Unknown(command),
        };
    }

    private static int Execute(List<string> args, bool clean, bool dry)
    {
        var profile = Value(args, "--profile") ?? "standard";
        var only = Split(Value(args, "--only"));
        var exclude = Split(Value(args, "--exclude"));
        var export = Value(args, "--export");
        var yes = args.Contains("-y") || args.Contains("--yes");
        if (!ModuleCatalog.ProfileNames.Contains(profile) && only.Count == 0)
        {
            Console.Error.WriteLine("Unknown profile " + profile);
            return 2;
        }
        Console.WriteLine(AppInfo.Name + " v" + AppInfo.Version);
        Console.WriteLine(Admin.IsAdmin() ? "Administrator: YES" : "Administrator: NO");
        Console.WriteLine(WindowsInfo.Banner());
        Console.WriteLine(Disclaimer.Short);
        var modules = ModuleCatalog.Select(only, exclude, profile);
        if (modules.Count == 0)
        {
            Console.Error.WriteLine("No modules selected.");
            return 2;
        }
        if (clean && !dry && !yes)
        {
            Console.Write("Type YES to clean: ");
            if (!string.Equals(Console.ReadLine()?.Trim(), "YES", StringComparison.Ordinal))
                return 1;
        }
        var cleaner = new Cleaner(modules);
        var report = clean
            ? cleaner.Clean(dry, Console.WriteLine, onlyIds: null, includeUnchecked: false)
            : cleaner.Scan(Console.WriteLine);
        foreach (var mod in report.Results)
        {
            if (mod.Items.Count == 0 && mod.Actions.Count == 0 && mod.Errors.Count == 0)
                continue;
            Console.WriteLine($"{mod.Label}: {mod.Items.Count} items, {Sizes.Format(mod.BytesEstimate)}, freed {Sizes.Format(mod.BytesFreed)}, errors {mod.Errors.Count}");
            foreach (var item in mod.Items)
                Console.WriteLine($"  [{item.Status}] {item.Label} — {item.NextStep}");
            foreach (var error in mod.Errors)
                Console.WriteLine("  error: " + error);
        }
        if (report.VerifyCounts.Count > 0)
            Console.WriteLine("Verify: " + string.Join(", ", report.VerifyCounts.Select(p => $"{p.Key}={p.Value}")));
        if (!string.IsNullOrEmpty(export))
        {
            var path = Reports.Save(report, clean ? (dry ? "dry-run" : "clean") : "scan", export, export.EndsWith(".json", StringComparison.OrdinalIgnoreCase));
            Console.WriteLine("Wrote " + path);
        }
        return report.Results.Any(r => r.Errors.Count > 0) ? 1 : 0;
    }

    private static int Modules()
    {
        foreach (var mod in ModuleCatalog.All())
            Console.WriteLine($"{mod.Id}\t{RiskText.Of(mod.Risk)}\t{(mod.DefaultEnabled ? "on" : "opt-in")}\t{mod.Label}");
        return 0;
    }

    private static int Undo((int Ok, int Failed, List<string> Messages) result)
    {
        foreach (var line in result.Messages)
            Console.WriteLine(line);
        Console.WriteLine($"ok={result.Ok} failed={result.Failed}");
        return result.Failed == 0 ? 0 : 1;
    }

    private static int Text(string text)
    {
        Console.WriteLine(text);
        return 0;
    }

    private static int Unknown(string command)
    {
        Console.Error.WriteLine("Unknown command " + command);
        PrintHelp();
        return 2;
    }

    private static void PrintHelp()
    {
        Console.WriteLine("WindowsCleaner --cli <modules|scan|clean|undo-privacy|undo-startup|disclaimer>");
        Console.WriteLine("  --profile safe|standard|privacy|oem|disk|new_pc|debloat|ai|workstation|full");
        Console.WriteLine("  --only id,id   --exclude id,id   --dry-run   -y   --export file   --elevate");
    }

    private static string? Value(List<string> args, string name)
    {
        var index = args.IndexOf(name);
        return index >= 0 && index + 1 < args.Count ? args[index + 1] : null;
    }

    private static List<string> Split(string? text) =>
        string.IsNullOrWhiteSpace(text) ? [] : text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
}
