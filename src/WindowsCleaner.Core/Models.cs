namespace WindowsCleaner;

public static class AppInfo
{
    public const string Name = "Windows Cleaner";
    public const string Version = "2.0.0";
}

public enum Risk
{
    Safe,
    Moderate,
    Aggressive,
}

public static class RiskText
{
    public static string Of(Risk risk) => risk switch
    {
        Risk.Safe => "safe",
        Risk.Moderate => "moderate",
        Risk.Aggressive => "aggressive",
        _ => "safe",
    };
}

public sealed class CleanItem
{
    public required string Id { get; init; }
    public required string Label { get; init; }
    public string Detail { get; set; } = "";
    public long BytesEstimate { get; set; }
    public bool RequiresAdmin { get; set; }
    public string Effect { get; set; } = "";
    public string Repercussions { get; set; } = "";
    public string Status { get; set; } = "";
    public string NextStep { get; set; } = "";
    public string Risk { get; set; } = "";
    public bool DefaultInclude { get; set; } = true;
}

public sealed class ModuleResult
{
    public required string ModuleId { get; init; }
    public required string Label { get; init; }
    public List<CleanItem> Items { get; } = [];
    public long BytesFreed { get; set; }
    public List<string> Actions { get; } = [];
    public List<string> Errors { get; } = [];
    public bool DryRun { get; set; }
    public long BytesEstimate => Items.Sum(i => i.BytesEstimate);
}

public sealed class CleanReport
{
    public List<ModuleResult> Results { get; } = [];
    public bool DryRun { get; set; }
    public bool Admin { get; set; }
    public List<string> SkippedModules { get; } = [];
    public List<string> SkippedModuleIds { get; } = [];
    public Dictionary<string, int> VerifyCounts { get; set; } = [];
    public long BytesEstimate => Results.Sum(r => r.BytesEstimate);
    public long BytesFreed => Results.Sum(r => r.BytesFreed);
}

public abstract class CleanModule
{
    public abstract string Id { get; }
    public abstract string Label { get; }
    public abstract string Description { get; }
    public virtual Risk Risk => Risk.Safe;
    public virtual bool RequiresAdmin => false;
    public virtual bool DefaultEnabled => true;

    public abstract ModuleResult Scan(Action<string>? progress);

    public abstract ModuleResult Clean(
        bool dryRun,
        Action<string>? progress,
        IReadOnlySet<string>? onlyIds,
        bool includeUnchecked = false);
}

public sealed record PrivacySetting(string Id, string Label, string Hive, string Path, string Name, int Desired, string Description);
public sealed record NameReason(string Match, string Label, string Reason);
public sealed record ServiceReason(string Name, string Label, string Reason);
public sealed record TaskReason(string Path, string Label, string Reason);
public sealed record StartupServiceSpec(string Name, string Label, string Reason, string Target, string KeepIf, bool PerUser);

public sealed class DeleteResult
{
    public int DeletedFiles { get; set; }
    public int DeletedDirs { get; set; }
    public long BytesFreed { get; set; }
    public List<string> Errors { get; } = [];
}

public sealed record RegChange(string Hive, string Path, string Name, object? Value, object? Previous, bool Ok, string? Error);

public static class ItemFilter
{
    public static bool Allow(string itemId, IReadOnlySet<string>? onlyIds) =>
        onlyIds is null || onlyIds.Contains(itemId);

    public static List<CleanItem> Filter(IEnumerable<CleanItem> items, IReadOnlySet<string>? onlyIds) =>
        onlyIds is null ? items.ToList() : items.Where(i => onlyIds.Contains(i.Id)).ToList();
}
