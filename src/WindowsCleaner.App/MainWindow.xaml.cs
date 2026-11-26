using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using WindowsCleaner;

namespace WindowsCleaner.App;

public partial class MainWindow : Window
{
    private readonly Dictionary<string, CheckBox> _modules = new();
    private readonly ObservableCollection<ResultRow> _rows = [];
    private CleanReport? _last;
    private string _lastMode = "scan";
    private bool _busy;

    public MainWindow()
    {
        InitializeComponent();
        Grid.ItemsSource = _rows;
        Subtitle.Text = $"Version {AppInfo.Version}. Choose a preset, scan, then keep only the rows you want.";
        EditionBanner.Text = WindowsInfo.Banner();
        var admin = Admin.IsAdmin();
        AdminLabel.Text = admin ? "Running as Administrator" : "Not running as Administrator";
        AdminLabel.Foreground = (System.Windows.Media.Brush)FindResource(admin ? "Primary" : "Danger");
        AdminPill.BorderBrush = (System.Windows.Media.Brush)FindResource(admin ? "Accent" : "Danger");
        foreach (var mod in ModuleCatalog.All())
        {
            var box = new CheckBox
            {
                Content = mod.Label,
                IsChecked = mod.DefaultEnabled,
                Tag = mod.Id,
                Margin = new Thickness(0, 4, 0, 4),
                ToolTip = $"{mod.Description}  Risk: {RiskText.Of(mod.Risk)}.",
            };
            box.Checked += (_, _) => RefreshTotals();
            box.Unchecked += (_, _) => RefreshTotals();
            _modules[mod.Id] = box;
            ModuleList.Children.Add(box);
        }
        ApplyProfile("standard");
        Grid.CellEditEnding += (_, _) => Dispatcher.BeginInvoke(RefreshTotals);
    }

    private void ApplyProfile(string profile)
    {
        var ids = ModuleCatalog.Select(null, null, profile).Select(m => m.Id).ToHashSet();
        foreach (var (id, box) in _modules)
            box.IsChecked = ids.Contains(id);
        MarkPreset(profile);
    }

    private void MarkPreset(string profile)
    {
        foreach (var panel in new[] { PresetList, IntentList })
        {
            foreach (var button in panel.Children.OfType<Button>())
                button.Style = (Style)FindResource((button.Tag as string) == profile ? "PresetOn" : typeof(Button));
        }
    }

    private List<CleanModule> Selected() =>
        ModuleCatalog.All().Where(m => _modules[m.Id].IsChecked == true).ToList();

    private void PresetSafe(object sender, RoutedEventArgs e) => ApplyProfile("safe");
    private void PresetStandard(object sender, RoutedEventArgs e) => ApplyProfile("standard");
    private void PresetPrivacy(object sender, RoutedEventArgs e) => ApplyProfile("privacy");
    private void PresetOem(object sender, RoutedEventArgs e) => ApplyProfile("oem");
    private void PresetFull(object sender, RoutedEventArgs e) => ApplyProfile("full");
    private void PresetDisk(object sender, RoutedEventArgs e) => ApplyProfile("disk");
    private void PresetNewPc(object sender, RoutedEventArgs e) => ApplyProfile("new_pc");
    private void PresetDebloat(object sender, RoutedEventArgs e) => ApplyProfile("debloat");
    private void PresetAi(object sender, RoutedEventArgs e) => ApplyProfile("ai");
    private void PresetWork(object sender, RoutedEventArgs e) => ApplyProfile("workstation");

    private async void ScanClick(object sender, RoutedEventArgs e) => await RunAsync(scan: true, dry: false);
    private async void DryRunClick(object sender, RoutedEventArgs e) => await RunAsync(scan: false, dry: true);
    private async void CleanClick(object sender, RoutedEventArgs e) => await RunAsync(scan: false, dry: false);

    private async Task RunAsync(bool scan, bool dry)
    {
        if (_busy)
            return;
        var modules = Selected();
        if (modules.Count == 0)
        {
            MessageBox.Show(this, "Choose at least one module.", AppInfo.Name, MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        Dictionary<string, IReadOnlySet<string>>? only = null;
        if (!scan)
        {
            only = CheckedIds();
            if (only.Values.All(set => set.Count == 0) && _rows.Count > 0)
            {
                MessageBox.Show(this, "Check at least one Clean? row.", AppInfo.Name, MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }
            if (!dry && !ConfirmClean(modules))
                return;
        }
        _busy = true;
        SetBusy(true);
        try
        {
            var report = await Task.Run(() =>
            {
                var cleaner = new Cleaner(modules);
                return scan
                    ? cleaner.Scan(Note)
                    : cleaner.Clean(dry, Note, only, includeUnchecked: false);
            });
            _last = report;
            _lastMode = scan ? "scan" : dry ? "dry-run" : "clean";
            ShowReport(report, keepChecks: !scan);
            var summary = scan
                ? $"Scan found {report.Results.Sum(r => r.Items.Count)} items, about {Sizes.Format(report.BytesEstimate)}."
                : $"{(dry ? "Dry-run" : "Clean")} finished. Freed {Sizes.Format(report.BytesFreed)}. {string.Join(", ", report.VerifyCounts.Select(p => $"{p.Key} {p.Value}"))}";
            StatusLine.Text = summary;
            if (!scan)
                MessageBox.Show(this, summary, AppInfo.Name, MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            StatusLine.Text = ex.Message;
            MessageBox.Show(this, ex.Message, AppInfo.Name, MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            _busy = false;
            SetBusy(false);
        }
    }

    private void Note(string message) => Dispatcher.Invoke(() => StatusLine.Text = message);

    private void ShowReport(CleanReport report, bool keepChecks)
    {
        var previous = _rows.ToDictionary(r => r.ModuleId + "::" + r.ItemId, r => r.Include);
        _rows.Clear();
        foreach (var mod in report.Results)
        {
            foreach (var item in mod.Items)
            {
                var key = mod.ModuleId + "::" + item.Id;
                var include = keepChecks && previous.TryGetValue(key, out var was) ? was : item.DefaultInclude;
                _rows.Add(new ResultRow
                {
                    Include = include,
                    Status = item.Status,
                    NextStep = item.NextStep,
                    Risk = TitleCase(string.IsNullOrEmpty(item.Risk) ? RiskText.Of(ModuleCatalog.All().First(m => m.Id == mod.ModuleId).Risk) : item.Risk),
                    Module = mod.Label,
                    Item = item.Label,
                    SizeText = Sizes.Format(item.BytesEstimate),
                    Effect = item.Effect,
                    Repercussions = item.Repercussions,
                    Detail = item.Detail,
                    ModuleId = mod.ModuleId,
                    ItemId = item.Id,
                    Bytes = item.BytesEstimate,
                });
            }
        }
        RefreshTotals();
    }

    private Dictionary<string, IReadOnlySet<string>> CheckedIds()
    {
        var map = new Dictionary<string, IReadOnlySet<string>>();
        foreach (var mod in Selected())
        {
            map[mod.Id] = _rows.Where(r => r.ModuleId == mod.Id && r.Include).Select(r => r.ItemId).ToHashSet();
        }
        return map;
    }

    private bool ConfirmClean(IReadOnlyList<CleanModule> modules)
    {
        if (!Admin.IsAdmin())
        {
            var needs = modules.Where(m => m.RequiresAdmin || ItemStatus.AdminModules.Contains(m.Id)).Select(m => m.Label).ToList();
            if (needs.Count > 0)
            {
                var answer = MessageBox.Show(this,
                    "These modules need Administrator or some of their rows will stay Failed — Needs Admin:\n\n" + string.Join("\n", needs) + "\n\nContinue anyway?",
                    AppInfo.Name, MessageBoxButton.YesNo, MessageBoxImage.Warning);
                if (answer != MessageBoxResult.Yes)
                    return false;
            }
        }
        if (_rows.Any(r => r.Include && r.ItemId == "windows_old"))
        {
            var answer = MessageBox.Show(this,
                "Windows.old is checked. Deleting it permanently removes the previous Windows install. Continue?",
                AppInfo.Name, MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (answer != MessageBoxResult.Yes)
                return false;
        }
        var aggressive = _rows.Where(r => r.Include && r.Risk == "aggressive").Select(r => r.Item).Take(12).ToList();
        var body = "Clean will change the checked rows, then re-scan.\n\n" + Disclaimer.Short;
        if (aggressive.Count > 0)
            body += "\n\nAggressive rows:\n" + string.Join("\n", aggressive);
        if (MessageBox.Show(this, body, "Confirm Clean", MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK)
            return false;
        if (RestoreCheck.IsChecked == true)
        {
            StatusLine.Text = "Creating a restore point...";
            var (ok, message) = Maintenance.CreateRestorePoint();
            StatusLine.Text = message;
            if (!ok && MessageBox.Show(this, message + "\n\nContinue without a new restore point?", AppInfo.Name, MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
                return false;
        }
        return true;
    }

    private void CleanAllClick(object sender, RoutedEventArgs e)
    {
        var checkAll = _rows.Count == 0 || _rows.Any(r => !r.Include);
        foreach (var row in _rows)
            row.Include = checkAll;
        RefreshTotals();
    }

    private void RowCleanClick(object sender, RoutedEventArgs e) => RefreshTotals();

    private void SyncCleanAll()
    {
        if (CleanAllBox is null)
            return;
        if (_rows.Count == 0 || _rows.All(r => !r.Include))
            CleanAllBox.IsChecked = false;
        else if (_rows.All(r => r.Include))
            CleanAllBox.IsChecked = true;
        else
            CleanAllBox.IsChecked = null;
    }

    private static string TitleCase(string value) =>
        string.IsNullOrEmpty(value) ? value : char.ToUpperInvariant(value[0]) + value[1..];

    private void UpdateEmpty()
    {
        var empty = _rows.Count == 0;
        EmptyHint.Visibility = empty ? Visibility.Visible : Visibility.Collapsed;
        if (!empty)
            return;
        EmptyHint.Text = _last is null
            ? "Scan to list what can be cleaned. Check the rows you want, then Dry-run."
            : "Nothing is listed for the selected modules.";
    }

    private void RefreshTotals()
    {
        SyncCleanAll();
        UpdateEmpty();
        var checkedRows = _rows.Where(r => r.Include).ToList();
        long safe = 0, moderate = 0, aggressive = 0;
        foreach (var row in checkedRows)
        {
            if (row.Risk == "moderate") moderate += row.Bytes;
            else if (row.Risk == "aggressive") aggressive += row.Bytes;
            else safe += row.Bytes;
        }
        Totals.Text = $"Checked {checkedRows.Count}  ·  Safe {Sizes.Format(safe)}  ·  Moderate {Sizes.Format(moderate)}  ·  Aggressive {Sizes.Format(aggressive)}";
    }

    private void SetBusy(bool busy)
    {
        IsEnabled = !busy;
    }

    private void ElevateClick(object sender, RoutedEventArgs e)
    {
        if (Admin.IsAdmin())
        {
            MessageBox.Show(this, "This window is already running as Administrator.", AppInfo.Name);
            return;
        }
        Admin.RelaunchAsAdmin();
        Close();
    }

    private void ExportClick(object sender, RoutedEventArgs e)
    {
        if (_last is null)
        {
            MessageBox.Show(this, "Scan or Clean first.", AppInfo.Name);
            return;
        }
        var dialog = new SaveFileDialog { Filter = "JSON (*.json)|*.json|Text (*.txt)|*.txt", FileName = "WindowsCleaner-report.json" };
        if (dialog.ShowDialog(this) != true)
            return;
        var path = Reports.Save(_last, _lastMode, dialog.FileName, dialog.FileName.EndsWith(".json", StringComparison.OrdinalIgnoreCase));
        StatusLine.Text = "Saved " + path;
    }

    private void UndoPrivacyClick(object sender, RoutedEventArgs e)
    {
        var (ok, failed, messages) = PrivacyUndo.UndoAll(dryRun: false);
        MessageBox.Show(this, $"Restored {ok}, failed {failed}.\n\n" + string.Join("\n", messages.Take(20)), AppInfo.Name);
    }

    private void UndoChangesClick(object sender, RoutedEventArgs e)
    {
        var (ok, failed, messages) = ChangeUndo.UndoAll(dryRun: false);
        MessageBox.Show(this, $"Restored {ok}, failed {failed}.\n\n" + string.Join("\n", messages.Take(20)), AppInfo.Name);
    }

    private void ScheduleClick(object sender, RoutedEventArgs e)
    {
        var (ok, message) = Maintenance.ScheduleWeeklyDisk();
        MessageBox.Show(this, message, AppInfo.Name, MessageBoxButton.OK, ok ? MessageBoxImage.Information : MessageBoxImage.Warning);
    }

    private void ShowHow(object sender, RoutedEventArgs e) =>
        MessageBox.Show(this, Disclaimer.How, "How this works", MessageBoxButton.OK, MessageBoxImage.Information);

    private void ShowDisclaimer(object sender, RoutedEventArgs e) =>
        MessageBox.Show(this, Disclaimer.Full, "Disclaimer", MessageBoxButton.OK, MessageBoxImage.Warning);
}

public sealed class ResultRow : INotifyPropertyChanged
{
    private bool _include;
    public bool Include
    {
        get => _include;
        set { _include = value; PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Include))); }
    }
    public string Status { get; set; } = "";
    public string NextStep { get; set; } = "";
    public string Risk { get; set; } = "";
    public string Module { get; set; } = "";
    public string Item { get; set; } = "";
    public string SizeText { get; set; } = "";
    public string Effect { get; set; } = "";
    public string Repercussions { get; set; } = "";
    public string Detail { get; set; } = "";
    public string ModuleId { get; set; } = "";
    public string ItemId { get; set; } = "";
    public long Bytes { get; set; }
    public event PropertyChangedEventHandler? PropertyChanged;
}
