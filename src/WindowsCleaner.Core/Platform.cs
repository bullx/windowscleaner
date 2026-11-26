using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace WindowsCleaner;

public static class Admin
{
    public static bool IsAdmin()
    {
        try
        {
            return IsUserAnAdmin();
        }
        catch
        {
            return false;
        }
    }

    public static void RelaunchAsAdmin()
    {
        var exe = Environment.ProcessPath ?? "";
        var args = string.Join(" ", Environment.GetCommandLineArgs().Skip(1).Select(Quote));
        ShellExecuteW(IntPtr.Zero, "runas", exe, args, null, 1);
    }

    public static string Quote(string arg) =>
        arg.Contains(' ') || arg.Contains('\t') ? $"\"{arg}\"" : arg;

    [DllImport("shell32.dll", SetLastError = true)]
    private static extern bool IsUserAnAdmin();

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr ShellExecuteW(IntPtr hwnd, string verb, string file, string? args, string? dir, int show);
}

public static class Proc
{
    public static ProcessResult Run(IReadOnlyList<string> args, int timeoutMs = 120_000)
    {
        if (args.Count == 0)
            return new ProcessResult(-1, "", "empty command");
        var psi = new ProcessStartInfo(args[0])
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (var arg in args.Skip(1))
            psi.ArgumentList.Add(arg);
        try
        {
            using var process = Process.Start(psi);
            if (process is null)
                return new ProcessResult(-1, "", "failed to start");
            // Read while the process runs. Waiting first deadlocks once the pipe fills.
            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(timeoutMs))
            {
                try { process.Kill(entireProcessTree: true); } catch { /* already gone */ }
                try { Task.WaitAll([stdoutTask, stderrTask], 2000); } catch { /* pipes closed */ }
                return new ProcessResult(-1, stdoutTask.IsCompletedSuccessfully ? stdoutTask.Result : "", "timed out");
            }
            process.WaitForExit();
            return new ProcessResult(process.ExitCode, stdoutTask.GetAwaiter().GetResult(), stderrTask.GetAwaiter().GetResult());
        }
        catch (Exception ex)
        {
            return new ProcessResult(-1, "", ex.Message);
        }
    }

    public static ProcessResult PowerShell(string script, int timeoutMs = 180_000) =>
        Run(["powershell", "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass", "-Command", script], timeoutMs);
}

public readonly record struct ProcessResult(int ExitCode, string Stdout, string Stderr)
{
    public string Tail => string.IsNullOrWhiteSpace(Stderr) ? Stdout.Trim() : Stderr.Trim();
}

public static class RegistryStore
{
    public static object? GetValue(string hive, string path, string name, object? fallback = null)
    {
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Default })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(Map(hive), view);
                using var key = baseKey.OpenSubKey(path, writable: false);
                if (key is null)
                    continue;
                var value = key.GetValue(name);
                if (value is not null)
                    return value;
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
        return fallback;
    }

    public static bool ValuesMatch(object? current, object? desired)
    {
        if (current is null)
            return false;
        try
        {
            return Convert.ToInt64(current) == Convert.ToInt64(desired);
        }
        catch
        {
            return Equals(current, desired);
        }
    }

    public static RegChange SetDword(string hive, string path, string name, int value, bool dryRun)
    {
        var previous = GetValue(hive, path, name);
        if (dryRun)
            return new RegChange(hive, path, name, value, previous, true, null);
        string? last = null;
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Default })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(Map(hive), view);
                using var key = baseKey.CreateSubKey(path, writable: true);
                key.SetValue(name, value, RegistryValueKind.DWord);
                var written = GetValue(hive, path, name);
                if (ValuesMatch(written, value))
                    return new RegChange(hive, path, name, value, previous, true, null);
                last = $"write did not stick (read back {written})";
            }
            catch (Exception ex)
            {
                last = ex.Message;
            }
        }
        return new RegChange(hive, path, name, value, previous, false, last ?? "failed to write registry value");
    }

    public static (bool Ok, string? Error) DeleteValue(string hive, string path, string name)
    {
        string? last = null;
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Default })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(Map(hive), view);
                using var key = baseKey.OpenSubKey(path, writable: true);
                if (key is null)
                    return (false, "key missing");
                key.DeleteValue(name, throwOnMissingValue: false);
                return (true, null);
            }
            catch (Exception ex)
            {
                last = ex.Message;
            }
        }
        return (false, last);
    }

    public static List<(string Name, string Value, RegistryValueKind Kind)> EnumerateValues(string hive, string path)
    {
        var found = new List<(string, string, RegistryValueKind)>();
        foreach (var view in new[] { RegistryView.Registry64, RegistryView.Default })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(Map(hive), view);
                using var key = baseKey.OpenSubKey(path, writable: false);
                if (key is null)
                    continue;
                foreach (var name in key.GetValueNames())
                {
                    if (string.IsNullOrEmpty(name))
                        continue;
                    var kind = key.GetValueKind(name);
                    var value = key.GetValue(name)?.ToString() ?? "";
                    found.Add((name, value, kind));
                }
                if (found.Count > 0)
                    return found;
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
        return found;
    }

    public static void SetValue(string hive, string path, string name, object value, RegistryValueKind kind)
    {
        using var baseKey = RegistryKey.OpenBaseKey(Map(hive), RegistryView.Registry64);
        using var key = baseKey.CreateSubKey(path, writable: true);
        key.SetValue(name, value, kind);
    }

    private static RegistryHive Map(string hive) => hive switch
    {
        "HKLM" => RegistryHive.LocalMachine,
        "HKCU" => RegistryHive.CurrentUser,
        "HKU" => RegistryHive.Users,
        "HKCR" => RegistryHive.ClassesRoot,
        _ => throw new ArgumentException(hive),
    };
}

public static class Fs
{
    public static bool Exists(string path)
    {
        try { return File.Exists(path) || Directory.Exists(path); }
        catch { return false; }
    }

    public static DeleteResult DeletePath(string path, bool dryRun)
    {
        var result = new DeleteResult();
        FileAttributes attrs;
        try
        {
            attrs = File.GetAttributes(path);
        }
        catch (FileNotFoundException)
        {
            return result;
        }
        catch (Exception ex)
        {
            result.Errors.Add($"{path}: {ex.Message}");
            return result;
        }

        var reparse = attrs.HasFlag(FileAttributes.ReparsePoint);
        var directory = attrs.HasFlag(FileAttributes.Directory) && !reparse;
        if (!directory)
        {
            long size = 0;
            try { size = new FileInfo(path).Length; } catch { /* link or gone */ }
            if (dryRun)
            {
                result.DeletedFiles = 1;
                result.BytesFreed = size;
                return result;
            }
            try
            {
                File.SetAttributes(path, FileAttributes.Normal);
                File.Delete(path);
                result.DeletedFiles = 1;
                result.BytesFreed = size;
            }
            catch (Exception ex)
            {
                result.Errors.Add($"{path}: {ex.Message}");
            }
            return result;
        }

        var stack = new Stack<string>();
        var dirs = new Stack<string>();
        stack.Push(path);
        while (stack.Count > 0)
        {
            var current = stack.Pop();
            dirs.Push(current);
            IEnumerable<string> children;
            try
            {
                children = Directory.EnumerateFileSystemEntries(current);
            }
            catch
            {
                continue;
            }
            foreach (var child in children)
            {
                FileAttributes childAttrs;
                try { childAttrs = File.GetAttributes(child); }
                catch { continue; }
                if (childAttrs.HasFlag(FileAttributes.ReparsePoint) || !childAttrs.HasFlag(FileAttributes.Directory))
                {
                    long size = 0;
                    try { if (!childAttrs.HasFlag(FileAttributes.Directory)) size = new FileInfo(child).Length; } catch { }
                    if (dryRun)
                    {
                        result.DeletedFiles++;
                        result.BytesFreed += size;
                        continue;
                    }
                    try
                    {
                        File.SetAttributes(child, FileAttributes.Normal);
                        File.Delete(child);
                        result.DeletedFiles++;
                        result.BytesFreed += size;
                    }
                    catch (Exception ex)
                    {
                        result.Errors.Add($"{child}: {ex.Message}");
                    }
                }
                else
                {
                    stack.Push(child);
                }
            }
        }

        if (dryRun)
        {
            result.DeletedDirs += dirs.Count;
            return result;
        }
        while (dirs.Count > 0)
        {
            var dir = dirs.Pop();
            try
            {
                if (!Directory.EnumerateFileSystemEntries(dir).Any())
                {
                    Directory.Delete(dir);
                    result.DeletedDirs++;
                }
            }
            catch (Exception ex)
            {
                result.Errors.Add($"{dir}: {ex.Message}");
            }
        }
        return result;
    }

    public static DeleteResult ClearDirectory(string path, bool dryRun)
    {
        var result = new DeleteResult();
        if (!Directory.Exists(path))
            return result;
        string[] children;
        try { children = Directory.GetFileSystemEntries(path); }
        catch (Exception ex)
        {
            result.Errors.Add($"{path}: {ex.Message}");
            return result;
        }
        foreach (var child in children)
        {
            var part = DeletePath(child, dryRun);
            result.DeletedFiles += part.DeletedFiles;
            result.DeletedDirs += part.DeletedDirs;
            result.BytesFreed += part.BytesFreed;
            result.Errors.AddRange(part.Errors);
        }
        return result;
    }

    public static DeleteResult Merge(IEnumerable<DeleteResult> parts)
    {
        var all = new DeleteResult();
        foreach (var part in parts)
        {
            all.DeletedFiles += part.DeletedFiles;
            all.DeletedDirs += part.DeletedDirs;
            all.BytesFreed += part.BytesFreed;
            all.Errors.AddRange(part.Errors);
        }
        return all;
    }
}

public static class Sizes
{
    public const int DefaultMaxFiles = 80_000;

    public static string Format(long bytes)
    {
        double n = Math.Max(0, bytes);
        string[] units = ["B", "KB", "MB", "GB", "TB"];
        foreach (var unit in units)
        {
            if (n < 1024 || unit == "TB")
                return unit == "B" ? $"{(long)n} {unit}" : $"{n:0.0} {unit}";
            n /= 1024;
        }
        return $"{n:0.0} TB";
    }

    public static long PathSize(string path, int maxFiles = DefaultMaxFiles)
    {
        FileAttributes attrs;
        try { attrs = File.GetAttributes(path); }
        catch { return 0; }
        if (attrs.HasFlag(FileAttributes.ReparsePoint))
            return 0;
        if (!attrs.HasFlag(FileAttributes.Directory))
        {
            try { return new FileInfo(path).Length; }
            catch { return 0; }
        }
        long total = 0;
        var seen = 0;
        var stack = new Stack<string>();
        stack.Push(path);
        while (stack.Count > 0)
        {
            var current = stack.Pop();
            IEnumerable<string> children;
            try { children = Directory.EnumerateFileSystemEntries(current); }
            catch { continue; }
            foreach (var child in children)
            {
                FileAttributes childAttrs;
                try { childAttrs = File.GetAttributes(child); }
                catch { continue; }
                if (childAttrs.HasFlag(FileAttributes.ReparsePoint))
                    continue;
                if (childAttrs.HasFlag(FileAttributes.Directory))
                    stack.Push(child);
                else
                {
                    try { total += new FileInfo(child).Length; } catch { continue; }
                    if (++seen >= maxFiles)
                        return total;
                }
            }
        }
        return total;
    }
}

public static class Paths
{
    public static string Local() => Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
    public static string Roaming() => Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
    public static string Home() => Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    public static string WindowsDir() => Environment.GetEnvironmentVariable("WINDIR") ?? @"C:\Windows";
    public static string ProgramData() => Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
    public static string Temp() => Path.GetTempPath();
    public static string SystemDrive()
    {
        var drive = Environment.GetEnvironmentVariable("SystemDrive") ?? "C:";
        return drive.EndsWith(':') ? drive : drive + ":";
    }

    public static string AppDataDir()
    {
        var dir = Path.Combine(string.IsNullOrEmpty(Local()) ? Home() : Local(), "WindowsCleaner");
        Directory.CreateDirectory(dir);
        return dir;
    }

    public static string System32()
    {
        var windir = WindowsDir();
        var redirected = !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432"));
        return Path.Combine(windir, redirected ? "Sysnative" : "System32");
    }
}

public static class ShellUi
{
    private const uint NoConfirmation = 0x1;
    private const uint NoProgress = 0x2;
    private const uint NoSound = 0x4;

    public static long RecycleBinBytes()
    {
        var info = new ShQueryRbInfo { cbSize = (uint)Marshal.SizeOf<ShQueryRbInfo>() };
        var hr = SHQueryRecycleBinW(null, ref info);
        return hr == 0 ? Math.Max(0, info.i64Size) : 0;
    }

    public static int EmptyRecycleBin() =>
        SHEmptyRecycleBinW(IntPtr.Zero, null, NoConfirmation | NoProgress | NoSound);

    [StructLayout(LayoutKind.Sequential)]
    private struct ShQueryRbInfo
    {
        public uint cbSize;
        public long i64Size;
        public long i64NumItems;
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SHQueryRecycleBinW(string? root, ref ShQueryRbInfo info);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SHEmptyRecycleBinW(IntPtr hwnd, string? root, uint flags);
}

public static class ServiceControl
{
    public static (string? Start, string? State) State(string name)
    {
        var start = StartFromRegistry(name);
        if (start is null)
            return (null, null);
        var query = Proc.Run(["sc", "query", name], 15_000);
        return (start, query.ExitCode == 0 ? ParseStateLine(query.Stdout) : null);
    }

    public static string? StartFromRegistry(string name)
    {
        var value = RegistryStore.GetValue("HKLM", @"SYSTEM\CurrentControlSet\Services\" + name, "Start");
        if (value is null)
            return null;
        int start;
        try { start = Convert.ToInt32(value); }
        catch { return null; }
        var delayed = RegistryStore.GetValue("HKLM", @"SYSTEM\CurrentControlSet\Services\" + name, "DelayedAutostart");
        var isDelayed = delayed is not null && Convert.ToInt32(delayed) == 1;
        return start switch
        {
            0 => "BOOT_START",
            1 => "SYSTEM_START",
            2 => isDelayed ? "DELAYED_AUTO_START" : "AUTO_START",
            3 => "DEMAND_START",
            4 => "DISABLED",
            _ => null,
        };
    }

    public static Dictionary<string, string> QueryStates(string type)
    {
        var proc = Proc.Run(["sc", "query", "type=", type, "state=", "all"], 30_000);
        var states = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (proc.ExitCode != 0)
            return states;
        string? name = null;
        foreach (var line in proc.Stdout.Split('\n'))
        {
            var stripped = line.Trim();
            if (stripped.StartsWith("SERVICE_NAME:", StringComparison.OrdinalIgnoreCase))
                name = stripped.Split(':', 2)[1].Trim();
            else if (name is not null && stripped.StartsWith("STATE", StringComparison.OrdinalIgnoreCase) && stripped.Contains(':'))
            {
                states[name] = stripped.Split(':', 2)[1].Trim();
                name = null;
            }
        }
        return states;
    }

    public static Dictionary<string, bool> QueryScheduledTasks()
    {
        var proc = Proc.Run(["schtasks", "/Query", "/FO", "LIST"], 60_000);
        var enabled = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
        if (proc.ExitCode != 0 && string.IsNullOrWhiteSpace(proc.Stdout))
            return enabled;
        string? name = null;
        foreach (var line in proc.Stdout.Split('\n'))
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("TaskName:", StringComparison.OrdinalIgnoreCase))
                name = trimmed.Split(':', 2)[1].Trim();
            else if (name is not null && trimmed.StartsWith("Status:", StringComparison.OrdinalIgnoreCase))
            {
                var status = trimmed.Split(':', 2)[1].Trim();
                enabled[name] = !status.Equals("Disabled", StringComparison.OrdinalIgnoreCase);
                name = null;
            }
        }
        return enabled;
    }

    private static string? ParseStateLine(string stdout)
    {
        foreach (var line in stdout.Split('\n'))
        {
            if (line.Contains("STATE", StringComparison.OrdinalIgnoreCase) && line.Contains(':'))
                return line.Split(':', 2)[1].Trim();
        }
        return null;
    }

    public static string? NormalizeStart(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
            return null;
        var raw = text.Trim().ToLowerInvariant();
        if (raw is "auto" or "demand" or "disabled" or "delayed-auto" or "boot" or "system")
            return raw;
        var upper = text.ToUpperInvariant();
        if (upper.Contains("DELAYED")) return "delayed-auto";
        if (upper.Contains("AUTO")) return "auto";
        if (upper.Contains("DEMAND")) return "demand";
        if (upper.Contains("DISABLED")) return "disabled";
        if (upper.Contains("BOOT")) return "boot";
        if (upper.Contains("SYSTEM")) return "system";
        return null;
    }

    public static bool ShouldOffer(string? start, string? state, string target)
    {
        if (string.IsNullOrEmpty(start))
            return false;
        var upper = start.ToUpperInvariant();
        if (upper.Contains("DISABLED") || upper.Contains("BOOT") || upper.Contains("SYSTEM_START"))
            return false;
        var auto = upper.Contains("AUTO");
        var running = !string.IsNullOrEmpty(state) && state.Contains("RUNNING", StringComparison.OrdinalIgnoreCase);
        if (target == "disabled")
            return auto || running;
        if (target == "demand")
            return auto;
        return false;
    }

    public static IReadOnlyList<string> UserServiceNames()
    {
        var proc = Proc.Run(["sc", "query", "type=", "userservice", "state=", "all"], 30_000);
        if (proc.ExitCode != 0)
            return [];
        var names = new List<string>();
        foreach (var line in proc.Stdout.Split('\n'))
        {
            var stripped = line.Trim();
            if (stripped.StartsWith("SERVICE_NAME:", StringComparison.OrdinalIgnoreCase))
            {
                var name = stripped.Split(':', 2)[1].Trim();
                if (name.Length > 0)
                    names.Add(name);
            }
        }
        return names;
    }
}

public static partial class TextMatch
{
    [GeneratedRegex(@"oem\d+\.inf", RegexOptions.IgnoreCase)]
    public static partial Regex OemInf();
}
