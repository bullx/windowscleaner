using WindowsCleaner;
using Xunit;

namespace WindowsCleaner.Core.Tests;

public class BehaviorTests
{
    [Theory]
    [InlineData("standard", "bloatware", false)]
    [InlineData("standard", "temp_files", true)]
    [InlineData("standard", "startup_services", false)]
    [InlineData("full", "startup_services", false)]
    [InlineData("full", "bloatware", true)]
    [InlineData("full", "ai_history", false)]
    [InlineData("debloat", "startup_services", true)]
    [InlineData("debloat", "windows_features", true)]
    [InlineData("disk", "ai_caches", true)]
    [InlineData("disk", "ai_history", false)]
    [InlineData("ai", "ai_models", false)]
    [InlineData("privacy", "privacy", true)]
    [InlineData("new_pc", "bloatware_oem", true)]
    [InlineData("safe", "privacy", false)]
    public void Profiles_keep_opt_in_rules(string profile, string moduleId, bool expected) =>
        Assert.Equal(expected, ModuleCatalog.Select(null, null, profile).Any(m => m.Id == moduleId));

    [Fact]
    public void Full_leaves_manual_modules_off()
    {
        var ids = ModuleCatalog.Select(null, null, "full").Select(m => m.Id).ToHashSet();
        foreach (var manual in ModuleCatalog.ManualPreset)
            Assert.DoesNotContain(manual, ids);
    }

    [Fact]
    public void Startup_offer_skips_boot_and_already_manual()
    {
        Assert.False(ServiceControl.ShouldOffer(null, "RUNNING", "disabled"));
        Assert.False(ServiceControl.ShouldOffer("2   BOOT_START", "STOPPED", "disabled"));
        Assert.False(ServiceControl.ShouldOffer("3   DEMAND_START", "STOPPED", "demand"));
        Assert.True(ServiceControl.ShouldOffer("2   AUTO_START", "STOPPED", "demand"));
        Assert.True(ServiceControl.ShouldOffer("3   DEMAND_START", "RUNNING", "disabled"));
        Assert.False(ServiceControl.ShouldOffer("4   DISABLED", "STOPPED", "disabled"));
    }

    [Fact]
    public void Verify_marks_sticky_item_not_fixed_when_it_remains()
    {
        var cleaned = new ModuleResult { ModuleId = "privacy", Label = "Privacy" };
        cleaned.Items.Add(new CleanItem { Id = "cortana", Label = "Cortana", Status = "Applied" });
        var still = new ModuleResult { ModuleId = "privacy", Label = "Privacy" };
        still.Items.Add(new CleanItem { Id = "cortana", Label = "Cortana" });
        ItemStatus.Verify([cleaned], new Dictionary<string, ModuleResult> { ["privacy"] = still }, admin: true);
        Assert.Equal("Not fixed", cleaned.Items[0].Status);
    }

    [Fact]
    public void Verify_marks_cache_fixed_when_rescan_is_empty()
    {
        var cleaned = new ModuleResult { ModuleId = "temp_files", Label = "Temp" };
        cleaned.Items.Add(new CleanItem { Id = "user_temp", Label = "Temp", Status = "Cleaned" });
        var empty = new ModuleResult { ModuleId = "temp_files", Label = "Temp" };
        ItemStatus.Verify([cleaned], new Dictionary<string, ModuleResult> { ["temp_files"] = empty }, admin: false);
        Assert.Equal("Fixed", cleaned.Items[0].Status);
    }

    [Fact]
    public void Driver_parser_drops_the_package_a_device_is_using()
    {
        const string listed = """
            Published Name:     oem1.inf
            Provider Name:      Contoso
            Class Name:         Net
            Driver Version:     1.0
            Original Name:      net.inf

            Published Name:     oem2.inf
            Provider Name:      Contoso
            Class Name:         Net
            Driver Version:     2.0
            Original Name:      net2.inf
            """;
        const string devices = "Driver Name: oem1.inf";
        var old = SystemParsers.Superseded(SystemParsers.ParseDrivers(listed), SystemParsers.InUse(devices));
        Assert.Equal(["oem2.inf"], old.Select(p => p.Published).ToArray());
    }

    [Fact]
    public void Component_store_sums_reclaimable_lines()
    {
        var text = "Backups: 1.5 GB\nCache and Temporary Data: 200 MB\n";
        Assert.Equal((long)(1.5 * 1024 * 1024 * 1024) + 200L * 1024 * 1024, SystemParsers.ParseComponentStore(text));
    }

    [Fact]
    public void Language_pack_keeps_the_current_ui_language()
    {
        var rows = SystemParsers.SelectableFeatures(
            ["Language.Basic~~~en-US~0.0", "Language.Basic~~~fr-FR~0.0", "XPS.Viewer~~~~0.0", "SMB1Protocol"],
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "en-US" });
        Assert.Contains(rows, r => r.Label == "Language pack fr-FR");
        Assert.DoesNotContain(rows, r => r.Id.Contains("en-US", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(rows, r => r.Label == "XPS Viewer");
        Assert.DoesNotContain(rows, r => r.Id.Contains("SMB1", StringComparison.Ordinal));
    }

    [Fact]
    public void Ai_allowlist_refuses_settings_and_program_files()
    {
        Assert.False(AiPaths.Allowed(@"C:\Program Files\Cursor\Cache"));
        Assert.False(AiPaths.Allowed(@"C:\Users\me\.claude\settings.json"));
        Assert.False(AiPaths.Allowed(@"C:\Users\me\.cursor\skills"));
        Assert.True(AiPaths.Allowed(@"C:\Users\me\.claude\cache"));
    }

    [Fact]
    public void Bloat_match_does_not_treat_store_as_bloat()
    {
        Assert.True(Catalogs.Bloat.Any(b => PackageMatch.Matches("Clipchamp.Clipchamp_1.0", b.Match)));
        Assert.DoesNotContain(Catalogs.Bloat, b => b.Match.Contains("WindowsStore", StringComparison.OrdinalIgnoreCase));
        Assert.DoesNotContain(Catalogs.StartupServices, s => s.Name is "WinDefend" or "wuauserv" or "Audiosrv" or "WlanSvc");
    }
}
