namespace WindowsCleaner;

public static class AiPaths
{
    public static readonly HashSet<string> ForbiddenFiles = new(StringComparer.OrdinalIgnoreCase)
    {
        "auth.json", ".credentials.json", "settings.json", "settings.local.json", "config.toml", "config.json",
        "id_ed25519", "id_ed25519.pub", ".claude.json", "mcp.json", "mcp_config.json", "oauth_creds.json",
        "mcp-oauth-tokens.json", "gemini.md", "claude.md", "keybindings.json", "cli-config.json", "ide_state.json",
        "argv.json", ".gitignore", "local state", "preferences", "cline_mcp_settings.json",
    };

    public static readonly HashSet<string> ForbiddenDirs = new(StringComparer.OrdinalIgnoreCase)
    {
        "skills", "skills-cursor", "plugins", "extensions", "agents", "rules", "credentials",
        "config-presets", "user-files", "snippets",
    };

    private static readonly string[] Electron =
    [
        "Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache", "CachedData",
        "CachedExtensionVSIXs", "CachedProfilesData", "logs", "Crashpad", "sentry", "process-monitor", "blob_storage",
    ];

    private static readonly string[] Desktop = ["Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache", "logs", "Crashpad"];
    private static readonly (string Effect, string Reper) CacheCopy = ("Deletes local caches and logs for this app. Quit it first.", "The app recreates these. Logins, skills, settings, and the install stay.");
    private static readonly (string Effect, string Reper) HistoryCopy = ("Deletes local chats and session files for this app.", "Local chats are forgotten. Project source, settings, and credentials stay. Cloud chats are not touched.");
    private static readonly (string Effect, string Reper) ModelCopy = ("Deletes downloaded model weights.", "The weights must be downloaded again. The app stays installed. This row starts unchecked.");

    public static bool Allowed(string path)
    {
        var parts = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (parts.Any(p => p.Equals("program files", StringComparison.OrdinalIgnoreCase) || p.Equals("program files (x86)", StringComparison.OrdinalIgnoreCase)))
            return false;
        if (ForbiddenFiles.Contains(Path.GetFileName(path)))
            return false;
        return !parts.Any(ForbiddenDirs.Contains);
    }

    public static List<PathPlan> CachePlans() => Build(cache: true);
    public static List<PathPlan> HistoryPlans() => Build(cache: false);
    public static List<PathPlan> ModelPlans()
    {
        var home = Paths.Home();
        var rows = new List<PathPlan>();
        Add(rows, Plan("ollama_models", "Ollama model weights", Existing(Path.Combine(home, ".ollama", "models")), ModelCopy, false, 2_000_000));
        Add(rows, Plan("lmstudio_models", "LM Studio model weights", Existing(Path.Combine(home, ".lmstudio", "models")).Concat(Existing(Path.Combine(home, ".lmstudio", "hub"))).ToList(), ModelCopy, false, 2_000_000));
        return rows;
    }

    private static List<PathPlan> Build(bool cache)
    {
        var rows = new List<PathPlan>();
        var home = Paths.Home();
        var local = Paths.Local();
        var roaming = Paths.Roaming();
        var temp = Paths.Temp();
        if (cache)
        {
            Add(rows, Plan("cursor_roaming_cache", "Cursor caches and logs", Children(Path.Combine(roaming, "Cursor"), Electron), CacheCopy));
            Add(rows, Plan("cursor_temp", "Cursor temp and updater logs", Children(temp, ["cursor", "cursor-sandbox-cache"]).Concat(Glob(temp, "cursor-agent-logs-*")).Concat(Glob(temp, "cursor-inno-updater-*.log")).ToList(), CacheCopy));
            Add(rows, Plan("cursor_tracking", "Cursor local analytics cache", Children(Path.Combine(home, ".cursor"), ["ai-tracking"]).Concat(Glob(Path.Combine(home, ".cursor"), "statsig-cache.json*")).ToList(), CacheCopy));
            var claude = Env("CLAUDE_CONFIG_DIR", Path.Combine(home, ".claude"));
            Add(rows, Plan("claude_cache", "Claude Code caches and logs", Children(claude, ["cache", "debug", "logs", "paste-cache", "shell-snapshots", "session-env", "statsig", "todos"]), CacheCopy));
            Add(rows, Plan("claude_temp", "Claude Code temp", Existing(Env("CLAUDE_CODE_TMPDIR", Path.Combine(temp, "claude"))), CacheCopy));
            Add(rows, Plan("claude_desktop_cache", "Claude Desktop caches", Children(Path.Combine(roaming, "Claude"), Desktop), CacheCopy));
            Add(rows, Plan("claude_desktop_cache_local", "Claude Desktop local caches", Children(Path.Combine(local, "AnthropicClaude"), Desktop), CacheCopy));
            Add(rows, Plan("codex_cache", "Codex caches and logs", Children(Env("CODEX_HOME", Path.Combine(home, ".codex")), ["logs", "log", "cache", "tmp"]), CacheCopy));
            Add(rows, Plan("gemini_tmp", "Gemini CLI temp", Existing(Path.Combine(home, ".gemini", "tmp")), CacheCopy));
            Add(rows, Plan("copilot_cache", "GitHub Copilot CLI cache", Direct(Env("COPILOT_CACHE_HOME", Path.Combine(local, "copilot"))), CacheCopy));
            Add(rows, Plan("windsurf_cache", "Windsurf caches and logs", Children(Path.Combine(roaming, "Windsurf"), Desktop), CacheCopy));
            Add(rows, Plan("continue_index", "Continue index cache", Existing(Path.Combine(home, ".continue", "index")), CacheCopy));
            Add(rows, Plan("aider_cache", "Aider cache files", Aider(home), CacheCopy));
            Add(rows, Plan("chatgpt_cache", "ChatGPT desktop caches", Children(Path.Combine(roaming, "ChatGPT"), Desktop), CacheCopy));
            Add(rows, Plan("chatgpt_cache_alt", "ChatGPT desktop caches (alt)", Children(Path.Combine(roaming, "com.openai.chat"), Desktop), CacheCopy));
            Add(rows, Plan("jetbrains_ai_cache", "JetBrains AI logs", JetBrains(local), CacheCopy));
            Add(rows, Plan("ollama_logs", "Ollama logs", Glob(Path.Combine(local, "Ollama"), "*.log").Concat(Children(Path.Combine(local, "Ollama"), ["upgrade.log"])).ToList(), CacheCopy));
            Add(rows, Plan("lmstudio_cache", "LM Studio caches and server logs", Children(Path.Combine(roaming, "LM Studio"), Desktop).Concat(Existing(Path.Combine(home, ".lmstudio", "server-logs"))).ToList(), CacheCopy));
            return rows;
        }

        var gs = Path.Combine(roaming, "Cursor", "User", "globalStorage");
        Add(rows, Plan("cursor_global_state", "Cursor global chat database", Children(gs, ["state.vscdb", "state.vscdb-shm", "state.vscdb-wal", "anysphere.cursor-agent-host", "anysphere.cursor-agent-worker", "anysphere.cursor-commits"]), HistoryCopy));
        Add(rows, Plan("cursor_workspace_storage", "Cursor workspace chat state", Existing(Path.Combine(roaming, "Cursor", "User", "workspaceStorage")), HistoryCopy));
        var dot = Path.Combine(home, ".cursor");
        Add(rows, Plan("cursor_dot_projects", "Cursor agent transcripts", Existing(Path.Combine(dot, "projects")), HistoryCopy));
        Add(rows, Plan("cursor_chats", "Cursor chats", Existing(Path.Combine(dot, "chats")), HistoryCopy));
        Add(rows, Plan("cursor_acp_sessions", "Cursor agent sessions", Existing(Path.Combine(dot, "acp-sessions")), HistoryCopy));
        Add(rows, Plan("cursor_plans", "Cursor plans", Existing(Path.Combine(dot, "plans")), HistoryCopy));
        Add(rows, Plan("cursor_agent_stores", "Cursor agent stores", Existing(Path.Combine(local, "Cursor", "AgentStores")), HistoryCopy));
        var claudeHome = Env("CLAUDE_CONFIG_DIR", Path.Combine(home, ".claude"));
        Add(rows, Plan("claude_sessions", "Claude Code sessions", ClaudeSessions(claudeHome), HistoryCopy));
        Add(rows, Plan("claude_desktop_chats", "Claude Desktop chats", Children(Path.Combine(roaming, "Claude"), ["Local Storage", "IndexedDB", "Session Storage", "Network"]), HistoryCopy));
        Add(rows, Plan("claude_desktop_chats_local", "Claude Desktop local chats", Children(Path.Combine(local, "AnthropicClaude"), ["Local Storage", "IndexedDB", "Session Storage", "Network"]), HistoryCopy));
        Add(rows, Plan("claude_store_chats", "Claude Store app chats", ClaudeStore(local), HistoryCopy));
        var codex = Env("CODEX_HOME", Path.Combine(home, ".codex"));
        Add(rows, Plan("codex_sessions", "Codex sessions", Existing(Path.Combine(codex, "sessions")).Concat(Glob(codex, "state_*.sqlite*")).ToList(), HistoryCopy));
        Add(rows, Plan("gemini_chats", "Gemini CLI chats", Glob(Path.Combine(home, ".gemini", "tmp"), "*/chats").Concat(Glob(Path.Combine(home, ".gemini", "tmp"), "*/*/chats")).ToList(), HistoryCopy));
        Add(rows, Plan("copilot_sessions", "GitHub Copilot CLI sessions", Children(Env("COPILOT_HOME", Path.Combine(home, ".copilot")), ["session-state", "otel"]), HistoryCopy));
        var code = Path.Combine(roaming, "Code", "User", "globalStorage");
        Add(rows, Plan("vscode_ai_chats", "VS Code Copilot / Cline / Continue chats", Children(code, ["github.copilot-chat", "github.copilot", "saoudrizwan.claude-dev", "continue.continue", "rooveterinaryinc.roo-cline"]), HistoryCopy));
        Add(rows, Plan("windsurf_history", "Windsurf chats", Windsurf(home), HistoryCopy));
        Add(rows, Plan("continue_sessions", "Continue sessions", Existing(Path.Combine(home, ".continue", "sessions")), HistoryCopy));
        Add(rows, Plan("cline_sessions", "Cline sessions", Children(Path.Combine(home, ".cline"), ["data", "sessions", "session"]), HistoryCopy));
        Add(rows, Plan("chatgpt_chats", "ChatGPT desktop chats", Children(Path.Combine(roaming, "ChatGPT"), ["Local Storage", "IndexedDB"]), HistoryCopy));
        Add(rows, Plan("chatgpt_chats_alt", "ChatGPT desktop chats (alt)", Children(Path.Combine(roaming, "com.openai.chat"), ["Local Storage", "IndexedDB"]), HistoryCopy));
        Add(rows, Plan("lmstudio_chats", "LM Studio conversations", Existing(Path.Combine(home, ".lmstudio", "conversations")), HistoryCopy));
        return rows;
    }

    private static void Add(List<PathPlan> rows, PathPlan? plan)
    {
        if (plan is not null)
            rows.Add(plan);
    }

    private static PathPlan? Plan(string id, string label, List<string> paths, (string Effect, string Reper) copy, bool include = true, int? max = null)
    {
        var clean = paths.Where(Allowed).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if (clean.Count == 0)
            return null;
        return new PathPlan { Id = id, Label = label, Paths = clean, DefaultInclude = include, Effect = copy.Effect, Repercussions = copy.Reper, MaxFiles = max };
    }

    private static string Env(string name, string fallback)
    {
        var raw = Environment.GetEnvironmentVariable(name);
        return string.IsNullOrWhiteSpace(raw) ? fallback : raw.Trim();
    }

    private static List<string> Children(string parent, IEnumerable<string> names)
    {
        if (!Directory.Exists(parent))
            return [];
        Dictionary<string, string> present;
        try { present = Directory.EnumerateFileSystemEntries(parent).ToDictionary(p => Path.GetFileName(p)!, p => p, StringComparer.OrdinalIgnoreCase); }
        catch { return []; }
        var found = new List<string>();
        foreach (var name in names)
        {
            if (present.TryGetValue(name, out var hit) && Allowed(hit))
                found.Add(hit);
        }
        return found;
    }

    private static List<string> Direct(string path)
    {
        if (!Directory.Exists(path))
            return [];
        try { return Directory.EnumerateFileSystemEntries(path).Where(Allowed).ToList(); }
        catch { return []; }
    }

    private static List<string> Glob(string directory, string pattern)
    {
        if (!Directory.Exists(directory))
            return [];
        try { return Directory.EnumerateFileSystemEntries(directory, pattern).Where(Allowed).ToList(); }
        catch { return []; }
    }

    private static List<string> Existing(string path) => Allowed(path) && Fs.Exists(path) ? [path] : [];

    private static List<string> ClaudeSessions(string home)
    {
        var found = new List<string>();
        var projects = Path.Combine(home, "projects");
        if (Directory.Exists(projects))
        {
            try
            {
                foreach (var project in Directory.EnumerateFileSystemEntries(projects))
                {
                    if (!Directory.Exists(project))
                    {
                        if (Allowed(project))
                            found.Add(project);
                        continue;
                    }
                    foreach (var child in Directory.EnumerateFileSystemEntries(project))
                    {
                        if (Path.GetFileName(child).Equals("memory", StringComparison.OrdinalIgnoreCase))
                            continue;
                        if (Allowed(child))
                            found.Add(child);
                    }
                }
            }
            catch { }
        }
        foreach (var name in new[] { "history.jsonl", "file-history", "plans", "tasks", "sessions", "image-cache", "uploads", "usage-data", "dev-mods", "feedback", "feedback-bundles" })
            found.AddRange(Existing(Path.Combine(home, name)));
        return found;
    }

    private static List<string> ClaudeStore(string local)
    {
        var packages = Path.Combine(local, "Packages");
        var found = new List<string>();
        if (!Directory.Exists(packages))
            return found;
        try
        {
            foreach (var folder in Directory.EnumerateDirectories(packages))
            {
                var name = Path.GetFileName(folder).ToLowerInvariant();
                if (!(name.StartsWith("claude_") || (name.Contains("anthropic") && name.Contains("claude"))))
                    continue;
                found.AddRange(Existing(Path.Combine(folder, "LocalState")));
                found.AddRange(Existing(Path.Combine(folder, "LocalCache")));
            }
        }
        catch { }
        return found;
    }

    private static List<string> Windsurf(string home)
    {
        var found = new List<string>();
        var codeium = Path.Combine(home, ".codeium", "windsurf");
        if (Directory.Exists(codeium))
        {
            try
            {
                foreach (var child in Directory.EnumerateFileSystemEntries(codeium))
                {
                    var low = Path.GetFileName(child).ToLowerInvariant();
                    if ((low.Contains("memory") || low.Contains("chat") || low.Contains("dump")) && Allowed(child))
                        found.Add(child);
                }
            }
            catch { }
        }
        var windsurf = Path.Combine(home, ".windsurf");
        if (Directory.Exists(windsurf))
        {
            try
            {
                foreach (var child in Directory.EnumerateFileSystemEntries(windsurf))
                {
                    var name = Path.GetFileName(child);
                    if (name.Equals("rules", StringComparison.OrdinalIgnoreCase) || name.Equals("mcp_config.json", StringComparison.OrdinalIgnoreCase))
                        continue;
                    if (Allowed(child))
                        found.Add(child);
                }
            }
            catch { }
        }
        return found;
    }

    private static List<string> Aider(string home)
    {
        if (!Directory.Exists(home))
            return [];
        try
        {
            return Directory.EnumerateFiles(home, ".aider*")
                .Where(p => Path.GetFileName(p).Contains("cache", StringComparison.OrdinalIgnoreCase) && Allowed(p))
                .ToList();
        }
        catch { return []; }
    }

    private static List<string> JetBrains(string local)
    {
        var root = Path.Combine(local, "JetBrains");
        var found = new List<string>();
        if (!Directory.Exists(root))
            return found;
        try
        {
            foreach (var ide in Directory.EnumerateDirectories(root))
            {
                found.AddRange(Existing(Path.Combine(ide, "llm-jcp-outbox")));
                found.AddRange(Existing(Path.Combine(ide, "event-log-metadata", "llmc")));
            }
        }
        catch { }
        return found;
    }
}

public sealed class AiCachesModule : CleanModule
{
    public override string Id => "ai_caches";
    public override string Label => "AI Caches & Logs";
    public override string Description => "Local caches and logs for Cursor, Claude, Codex, Copilot, Windsurf, and similar tools, plus Ollama and LM Studio logs. Does not delete chats, model weights, logins, skills, or settings.";
    public override bool DefaultEnabled => false;
    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, AiPaths.CachePlans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, AiPaths.CachePlans(), dryRun, progress, onlyIds, includeUnchecked);
}

public sealed class AiHistoryModule : CleanModule
{
    public override string Id => "ai_history";
    public override string Label => "AI Chats & Sessions";
    public override string Description => "Local chat transcripts and session files for Cursor, Claude, Codex, and similar tools. Project source, settings, skills, and cloud chats stay. Opt-in; not part of Full.";
    public override Risk Risk => Risk.Moderate;
    public override bool DefaultEnabled => false;
    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, AiPaths.HistoryPlans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, AiPaths.HistoryPlans(), dryRun, progress, onlyIds, includeUnchecked);
}

public sealed class AiModelsModule : CleanModule
{
    public override string Id => "ai_models";
    public override string Label => "AI Model Weights";
    public override string Description => "Ollama and LM Studio downloaded weights. Rows start unchecked. Deleting them means downloading the models again. The apps stay installed.";
    public override Risk Risk => Risk.Aggressive;
    public override bool DefaultEnabled => false;
    public override ModuleResult Scan(Action<string>? progress) => PathRows.Scan(this, AiPaths.ModelPlans(), progress);
    public override ModuleResult Clean(bool dryRun, Action<string>? progress, IReadOnlySet<string>? onlyIds, bool includeUnchecked = false) =>
        PathRows.Clean(this, AiPaths.ModelPlans(), dryRun, progress, onlyIds, includeUnchecked);
}
