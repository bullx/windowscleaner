"""Tkinter desktop UI - light theme, step-based cleanup flow."""

from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from windowscleaner import __app_name__, __version__
from windowscleaner.cleaner import CleanReport, Cleaner
from windowscleaner.disclaimer import DISCLAIMER_FULL, DISCLAIMER_SHORT
from windowscleaner.modules import all_modules
from windowscleaner.modules.base import CleanModule, Risk
from windowscleaner.utils.admin import is_admin, relaunch_as_admin
from windowscleaner.utils.size import format_bytes

# Light theme tokens (readable Windows Settings-like palette)
C = {
    "bg": "#f3f4f6",
    "card": "#ffffff",
    "border": "#d1d5db",
    "text": "#111827",
    "muted": "#4b5563",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "safe": "#15803d",
    "moderate": "#a16207",
    "aggressive": "#b91c1c",
    "admin_yes": "#15803d",
    "admin_no": "#b45309",
    "row_alt": "#f9fafb",
    "select": "#dbeafe",
    "log_bg": "#f8fafc",
}

# Results table columns: id -> (heading, default_width, min_width)
RESULT_COLUMNS: dict[str, tuple[str, int, int]] = {
    "status": ("Status", 130, 90),
    "next_step": ("What to do", 260, 120),
    "module": ("Module", 130, 80),
    "item": ("Item", 170, 90),
    "size": ("Size", 85, 60),
    "effect": ("What it does", 240, 120),
    "repercussions": ("Repercussions", 240, 120),
    "detail": ("Path / detail", 260, 120),
}
DEFAULT_VISIBLE_COLUMNS = [
    "status",
    "next_step",
    "module",
    "item",
    "size",
    "effect",
    "repercussions",
]

PROFILE_IDS = {
    "safe": lambda m: m.risk == Risk.SAFE and m.default_enabled,
    "standard": lambda m: m.default_enabled
    and m.id not in {"bloatware", "bloatware_oem", "perf_services"},
    "privacy": lambda m: m.id in {"privacy", "tracking", "telemetry_services"},
    "oem": lambda m: m.id in {"bloatware", "bloatware_oem"},
    "full": lambda m: m.id != "perf_services",
}

HOW_IT_WORKS = """How cleanup actually works (all public Windows mechanisms)

Nothing here is a secret exploit. The tool uses documented Windows folders, registry policy keys, services, scheduled tasks, and PowerShell AppX commands.

Community sources this app aligns with (public, widely used):
  - Win11Debloat (Raphire) - telemetry, Copilot/Recall/Click-to-Do, Paint/Notepad/Edge AI, Widgets, app removal + provisioned packages
  - Chris Titus WinUtil - Delivery Optimization, DiagTrack, privacy registry keys
  - O&O ShutUp10++ style - recommended privacy toggles + restore-point safety
  - Sophia Script - CEIP / diagnosis scheduled tasks, SoftwareDistribution cleanup
  - Popular cleaners - browser caches, GPU/DirectX shader caches, temp/WER paths

What each category does:
1) Temp / caches / logs / tracking folders
   Delete files under known paths (%TEMP%, SoftwareDistribution\\Download, WER, Timeline DBs, WebCache, Edge/Chrome/Firefox caches, D3DSCache, Windows.old, ...)

2) Recycle Bin - Shell API SHEmptyRecycleBin

3) Privacy hardening - registry/policy values (AllowTelemetry, Copilot/Recall/Click-to-Do, Paint/Notepad/Edge AI, Widgets, DODownloadMode, Find My Device, suggestion switches)

4) Telemetry services & tasks - sc config start= disabled + schtasks /Disable (DiagTrack, CEIP, Flighting, PushToInstall, Maps, Device Information, ...)

5) Bloatware (opt-in) - Remove-AppxPackage + Remove-AppxProvisionedPackage (Win11Debloat-style list)
6) OEM / Win32 (opt-in) - OEM AppX families + winget uninstall (SupportAssist, Vantage, Wolf, …)
7) Optional perf services (opt-in, not in Full) - SysMain / WSearch disable

Safety notes from the community:
  - Prefer Scan + Dry-run first
  - Create a System Restore point before Clean (checkbox in the UI)
  - Do NOT disable Windows Defender / Windows Update (this tool never does)
  - Aggressive one-click scripts online can break WinRE / updates - we stay modular and selectable
  - See Disclaimer (button) — use at your own risk; not affiliated with Microsoft

Why Scan can still show items after Clean:
  - Temp, browser, and GPU caches refill as soon as apps run
  - Some files are locked (in use) and cannot be deleted until reboot
  - Privacy/service changes need Administrator - without it they stay unchanged
  - DNS flush is temporary by design (entries come back while browsing)
  - Applied privacy settings should DISAPPEAR from Scan (if they still show, they were not applied)
"""


class WindowsCleanerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{__app_name__} v{__version__}")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg=C["bg"])

        self._modules = all_modules()
        self._vars: dict[str, tk.BooleanVar] = {}
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._last_report: CleanReport | None = None
        self._row_data: dict[str, dict[str, str]] = {}
        self._visible_columns = self._load_visible_columns()
        self._column_widths = self._load_column_widths()

        self._build_style()
        self._build_layout()
        self._apply_profile("standard")
        self.after(120, self._poll_queue)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=C["bg"], foreground=C["text"], font=("Segoe UI", 10))
        style.configure("TFrame", background=C["bg"])
        style.configure("Card.TFrame", background=C["card"])
        style.configure("TLabel", background=C["bg"], foreground=C["text"])
        style.configure("Card.TLabel", background=C["card"], foreground=C["text"])
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground=C["text"], background=C["bg"])
        style.configure("Sub.TLabel", foreground=C["muted"], font=("Segoe UI", 9), background=C["bg"])
        style.configure("CardSub.TLabel", foreground=C["muted"], font=("Segoe UI", 9), background=C["card"])
        style.configure("AdminYes.TLabel", foreground=C["admin_yes"], font=("Segoe UI", 9, "bold"), background=C["bg"])
        style.configure("AdminNo.TLabel", foreground=C["admin_no"], font=("Segoe UI", 9, "bold"), background=C["bg"])
        style.configure("Step.TLabel", font=("Segoe UI", 9, "bold"), foreground=C["accent"], background=C["bg"])
        style.configure("CardStep.TLabel", font=("Segoe UI", 9, "bold"), foreground=C["accent"], background=C["card"])

        style.configure(
            "TButton",
            padding=(10, 7),
            font=("Segoe UI", 9),
            background="#e5e7eb",
            foreground=C["text"],
            bordercolor=C["border"],
            lightcolor="#e5e7eb",
            darkcolor="#e5e7eb",
        )
        style.map("TButton", background=[("active", "#d1d5db"), ("disabled", "#f3f4f6")])

        style.configure(
            "Accent.TButton",
            padding=(10, 8),
            font=("Segoe UI", 10, "bold"),
            background=C["accent"],
            foreground="#ffffff",
            bordercolor=C["accent"],
            lightcolor=C["accent"],
            darkcolor=C["accent"],
        )
        style.map(
            "Accent.TButton",
            background=[("active", C["accent_hover"]), ("disabled", "#93c5fd")],
            foreground=[("disabled", "#f8fafc")],
        )

        style.configure(
            "Danger.TButton",
            padding=(10, 8),
            font=("Segoe UI", 10, "bold"),
            background="#dc2626",
            foreground="#ffffff",
            bordercolor="#dc2626",
            lightcolor="#dc2626",
            darkcolor="#dc2626",
        )
        style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#fca5a5")])

        style.configure(
            "TCheckbutton",
            background=C["card"],
            foreground=C["text"],
            font=("Segoe UI", 10),
            focuscolor=C["card"],
        )
        style.map("TCheckbutton", background=[("active", C["card"])])

        style.configure("TLabelframe", background=C["card"], foreground=C["text"], bordercolor=C["border"])
        style.configure(
            "TLabelframe.Label",
            background=C["card"],
            foreground=C["text"],
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "Treeview",
            background=C["card"],
            foreground=C["text"],
            fieldbackground=C["card"],
            rowheight=26,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#e5e7eb",
            foreground=C["text"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", C["select"])],
            foreground=[("selected", C["text"])],
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#e5e7eb",
            background=C["accent"],
            bordercolor="#e5e7eb",
            lightcolor=C["accent"],
            darkcolor=C["accent"],
        )
        style.configure("TScrollbar", background="#e5e7eb", troughcolor=C["card"], bordercolor=C["border"])
        style.configure("TSeparator", background=C["border"])

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text=__app_name__, style="Header.TLabel").pack(side=tk.LEFT)
        right_h = ttk.Frame(header)
        right_h.pack(side=tk.RIGHT)
        self.admin_label = ttk.Label(right_h, text="", style="AdminNo.TLabel")
        self.admin_label.pack(side=tk.TOP, anchor=tk.E)
        ttk.Button(right_h, text="How this works", command=self._show_how).pack(side=tk.TOP, anchor=tk.E, pady=(4, 0))
        ttk.Button(right_h, text="Disclaimer", command=self._show_disclaimer).pack(
            side=tk.TOP, anchor=tk.E, pady=(4, 0)
        )
        self._refresh_admin()

        ttk.Label(
            root,
            text="Step through: choose what to clean  →  scan  →  dry-run  →  clean. Aggressive items stay off until you enable them.",
            style="Sub.TLabel",
        ).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(
            root,
            text=DISCLAIMER_SHORT,
            style="Sub.TLabel",
            wraplength=900,
        ).pack(anchor=tk.W, pady=(0, 10))

        body = ttk.Frame(root)
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left_inner = ttk.Frame(left, style="Card.TFrame", padding=12)
        left_inner.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_module_panel(left_inner)
        self._build_action_panel(left_inner)
        self._build_results_panel(right)
        self._build_status_bar(root)

    def _build_module_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="1. Choose what to clean", style="CardStep.TLabel").pack(anchor=tk.W)
        ttk.Label(
            parent,
            text="Quick presets, or tick modules one by one.",
            style="CardSub.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        profile_row = ttk.Frame(parent, style="Card.TFrame")
        profile_row.pack(fill=tk.X, pady=(0, 8))
        for name, key in (
            ("Safe", "safe"),
            ("Standard", "standard"),
            ("Privacy", "privacy"),
            ("OEM", "oem"),
            ("Full", "full"),
        ):
            ttk.Button(profile_row, text=name, command=lambda k=key: self._apply_profile(k), width=9).pack(
                side=tk.LEFT, padx=(0, 4)
            )

        box = ttk.LabelFrame(parent, text="Modules", padding=8)
        box.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(box, bg=C["card"], highlightthickness=0, width=360)
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, style="Card.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def _sync_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        canvas.bind("<Configure>", _sync_width)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        risk_fg = {
            "safe": C["safe"],
            "moderate": C["moderate"],
            "aggressive": C["aggressive"],
        }

        for mod in self._modules:
            var = tk.BooleanVar(
                value=mod.default_enabled
                and mod.id not in {"bloatware", "bloatware_oem", "perf_services"}
            )
            self._vars[mod.id] = var

            row = tk.Frame(inner, bg=C["card"], pady=6)
            row.pack(fill=tk.X, anchor=tk.W)

            cb = ttk.Checkbutton(row, text=mod.label, variable=var, command=self._on_selection_changed)
            cb.pack(anchor=tk.W)

            badges = [mod.risk.value.upper()]
            if mod.requires_admin:
                badges.append("ADMIN")
            if not mod.default_enabled:
                badges.append("OPT-IN")
            ttk.Label(
                row,
                text="  ·  ".join(badges),
                foreground=risk_fg.get(mod.risk.value, C["muted"]),
                background=C["card"],
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor=tk.W, padx=(24, 0))
            ttk.Label(
                row,
                text=mod.description,
                style="CardSub.TLabel",
                wraplength=310,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=(24, 0), pady=(2, 0))

            tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X, pady=(2, 0))

        btn_row = ttk.Frame(parent, style="Card.TFrame")
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Select all", command=lambda: self._set_all(True)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="Select none", command=lambda: self._set_all(False)).pack(side=tk.LEFT)

    def _build_action_panel(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)
        ttk.Label(parent, text="2. Preview & clean", style="CardStep.TLabel").pack(anchor=tk.W)
        ttk.Label(
            parent,
            text="Always scan first. Dry-run changes nothing.",
            style="CardSub.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        self.scan_btn = ttk.Button(parent, text="Scan selected", style="Accent.TButton", command=self._on_scan)
        self.scan_btn.pack(fill=tk.X, pady=3)
        self.dry_btn = ttk.Button(parent, text="Dry-run (no changes)", command=lambda: self._on_clean(dry_run=True))
        self.dry_btn.pack(fill=tk.X, pady=3)
        self.clean_btn = ttk.Button(
            parent,
            text="Clean selected",
            style="Danger.TButton",
            command=lambda: self._on_clean(dry_run=False),
        )
        self.clean_btn.pack(fill=tk.X, pady=3)

        self.restore_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            parent,
            text="Create System Restore point before Clean",
            variable=self.restore_var,
        ).pack(anchor=tk.W, pady=(8, 2))
        ttk.Label(
            parent,
            text="Recommended by ShutUp10-style guides. Needs Admin + System Restore enabled.",
            style="CardSub.TLabel",
            wraplength=320,
        ).pack(anchor=tk.W)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.elevate_btn = ttk.Button(parent, text="Restart as Administrator", command=self._on_elevate)
        self.elevate_btn.pack(fill=tk.X, pady=2)

        self.progress = ttk.Progressbar(parent, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(10, 4))
        self.progress_label = ttk.Label(parent, text="Ready", style="CardSub.TLabel")
        self.progress_label.pack(anchor=tk.W)

    def _build_results_panel(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text="3. Results", style="Step.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Customize columns", command=self._customize_columns).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(header, text="Reset column widths", command=self._reset_column_widths).pack(
            side=tk.RIGHT
        )

        self.summary_var = tk.StringVar(value="Select modules on the left, then click Scan.")
        ttk.Label(parent, textvariable=self.summary_var, style="Sub.TLabel", wraplength=620).pack(
            anchor=tk.W, pady=(2, 4)
        )
        ttk.Label(
            parent,
            text="Drag column edges to resize. Shift+mouse wheel scrolls sideways. Customize columns to show/hide.",
            style="Sub.TLabel",
        ).pack(anchor=tk.W, pady=(0, 6))

        tree_wrap = tk.Frame(parent, bg=C["border"], padx=1, pady=1)
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        tree_frame = ttk.Frame(tree_wrap, style="Card.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Keep ALL column ids registered so we can show/hide without losing data mapping.
        all_cols = tuple(RESULT_COLUMNS.keys())
        self.tree = ttk.Treeview(
            tree_frame,
            columns=all_cols,
            show="headings",
            selectmode="browse",
        )
        for col, (title, width, min_w) in RESULT_COLUMNS.items():
            self.tree.heading(col, text=title, command=lambda c=col: self._sort_by_column(c))
            saved_w = self._column_widths.get(col, width)
            # stretch=False is required for horizontal scrolling to work
            self.tree.column(
                col,
                width=saved_w,
                minwidth=min_w,
                stretch=False,
                anchor=tk.E if col == "size" else tk.W,
            )

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Shift-MouseWheel>", self._on_tree_shift_wheel)
        self.tree.bind("<ButtonRelease-1>", self._on_column_resize_done)

        self._yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self._xscroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=self._yscroll.set, xscrollcommand=self._xscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self._yscroll.grid(row=0, column=1, sticky="ns")
        self._xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._apply_visible_columns()

        detail_box = ttk.LabelFrame(parent, text="Selected item (full text)", padding=6)
        detail_box.pack(fill=tk.X, pady=(8, 0))
        self.item_detail = tk.Text(
            detail_box,
            height=5,
            wrap=tk.WORD,
            bg=C["card"],
            fg=C["text"],
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        self.item_detail.pack(fill=tk.X)
        self.item_detail.insert(
            "1.0",
            "Click a row to read the full effect and repercussions.",
        )
        self.item_detail.configure(state=tk.DISABLED)

        log_box = ttk.LabelFrame(parent, text="Activity log", padding=6)
        log_box.pack(fill=tk.BOTH, pady=(10, 0))
        self.log = tk.Text(
            log_box,
            height=7,
            wrap=tk.WORD,
            bg=C["log_bg"],
            fg=C["text"],
            insertbackground=C["text"],
            relief=tk.FLAT,
            font=("Consolas", 9),
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.configure(state=tk.DISABLED)

    def _prefs_path(self) -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WindowsCleaner"
        base.mkdir(parents=True, exist_ok=True)
        return base / "ui_prefs.json"

    def _load_prefs(self) -> dict:
        try:
            path = self._prefs_path()
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_prefs(self) -> None:
        data = {
            "visible_columns": self._visible_columns,
            "column_widths": {
                col: int(self.tree.column(col, "width"))
                for col in RESULT_COLUMNS
                if hasattr(self, "tree")
            },
        }
        # Merge widths from memory if tree not ready
        if not data["column_widths"]:
            data["column_widths"] = self._column_widths
        try:
            self._prefs_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_visible_columns(self) -> list[str]:
        prefs = self._load_prefs()
        cols = prefs.get("visible_columns")
        if isinstance(cols, list):
            filtered = [c for c in cols if c in RESULT_COLUMNS]
            # Ensure new status columns appear even if old prefs lack them
            for required in ("status", "next_step"):
                if required not in filtered and required in RESULT_COLUMNS:
                    filtered.insert(0 if required == "status" else 1, required)
            if filtered:
                return filtered
        return list(DEFAULT_VISIBLE_COLUMNS)

    def _load_column_widths(self) -> dict[str, int]:
        prefs = self._load_prefs()
        widths = prefs.get("column_widths") or {}
        out: dict[str, int] = {}
        for col, (_t, default_w, min_w) in RESULT_COLUMNS.items():
            try:
                w = int(widths.get(col, default_w))
            except (TypeError, ValueError):
                w = default_w
            out[col] = max(min_w, w)
        return out

    def _apply_visible_columns(self) -> None:
        # At least one column must stay visible
        visible = [c for c in self._visible_columns if c in RESULT_COLUMNS]
        if not visible:
            visible = ["item"]
            self._visible_columns = visible
        self.tree.configure(displaycolumns=visible)
        # Re-assert stretch=False so horizontal scroll keeps working after customize
        for col in RESULT_COLUMNS:
            title, default_w, min_w = RESULT_COLUMNS[col]
            width = int(self.tree.column(col, "width") or self._column_widths.get(col, default_w))
            self.tree.column(
                col,
                width=width,
                minwidth=min_w,
                stretch=False,
                anchor=tk.E if col == "size" else tk.W,
            )
        self._save_prefs()

    def _customize_columns(self) -> None:
        win = tk.Toplevel(self)
        win.title("Customize result columns")
        win.geometry("360x340")
        win.configure(bg=C["bg"])
        win.transient(self)
        win.grab_set()

        ttk.Label(
            win,
            text="Choose which columns appear in Results.\nDrag column edges in the table to resize.",
            style="Sub.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=12, pady=10)

        vars_map: dict[str, tk.BooleanVar] = {}
        box = ttk.Frame(win)
        box.pack(fill=tk.BOTH, expand=True, padx=12)
        for col, (title, _w, _mw) in RESULT_COLUMNS.items():
            var = tk.BooleanVar(value=col in self._visible_columns)
            vars_map[col] = var
            ttk.Checkbutton(box, text=title, variable=var).pack(anchor=tk.W, pady=3)

        def apply() -> None:
            selected = [c for c, v in vars_map.items() if v.get()]
            if not selected:
                messagebox.showwarning(__app_name__, "Keep at least one column visible.", parent=win)
                return
            # Preserve preferred order from RESULT_COLUMNS
            self._visible_columns = [c for c in RESULT_COLUMNS if c in selected]
            self._apply_visible_columns()
            # Rebuild rows with current displaycolumns (values stay full-order)
            if self._last_report is not None:
                mode = "scan"
                self._fill_report(self._last_report, mode)
            win.destroy()

        def select_all() -> None:
            for v in vars_map.values():
                v.set(True)

        def select_minimal() -> None:
            for c, v in vars_map.items():
                v.set(c in {"status", "next_step", "module", "item", "size"})

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=12, pady=12)
        ttk.Button(btns, text="All", command=select_all).pack(side=tk.LEFT)
        ttk.Button(btns, text="Minimal", command=select_minimal).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Apply", style="Accent.TButton", command=apply).pack(side=tk.RIGHT, padx=4)

    def _reset_column_widths(self) -> None:
        for col, (_t, width, min_w) in RESULT_COLUMNS.items():
            self.tree.column(col, width=width, minwidth=min_w, stretch=False)
            self._column_widths[col] = width
        self._save_prefs()
        self.status_var.set("Column widths reset — drag edges to adjust")

    def _on_column_resize_done(self, _event=None) -> None:
        # Persist widths after user finishes dragging a separator
        try:
            for col in RESULT_COLUMNS:
                self._column_widths[col] = int(self.tree.column(col, "width"))
            self._save_prefs()
        except tk.TclError:
            pass

    def _on_tree_shift_wheel(self, event: tk.Event) -> str:
        # Horizontal scroll while holding Shift
        try:
            delta = -1 if event.delta > 0 else 1
            self.tree.xview_scroll(delta * 3, "units")
        except tk.TclError:
            pass
        return "break"

    def _sort_by_column(self, col: str) -> None:
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        reverse = getattr(self, "_sort_reverse", {}).get(col, False)
        rows.sort(key=lambda t: (t[0] or "").lower(), reverse=reverse)
        for idx, (_val, k) in enumerate(rows):
            self.tree.move(k, "", idx)
        if not hasattr(self, "_sort_reverse"):
            self._sort_reverse = {}
        self._sort_reverse[col] = not reverse

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        self.status_var = tk.StringVar(value="Ready")
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(bar, textvariable=self.status_var, style="Sub.TLabel").pack(side=tk.LEFT)

    def _on_tree_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        data = self._row_data.get(sel[0])
        if not data:
            # Fallback if row map missing
            vals = self.tree.item(sel[0], "values")
            keys = list(RESULT_COLUMNS.keys())
            data = {keys[i]: vals[i] for i in range(min(len(keys), len(vals)))}
        text = (
            f"Status: {data.get('status', '')}\n"
            f"What to do: {data.get('next_step', '')}\n\n"
            f"Module: {data.get('module', '')}\n"
            f"Item: {data.get('item', '')}\n"
            f"Size: {data.get('size', '')}\n\n"
            f"What it does:\n{data.get('effect', '')}\n\n"
            f"Repercussions:\n{data.get('repercussions', '')}\n\n"
            f"Path / detail:\n{data.get('detail', '')}"
        )
        self.item_detail.configure(state=tk.NORMAL)
        self.item_detail.delete("1.0", tk.END)
        self.item_detail.insert("1.0", text)
        self.item_detail.configure(state=tk.DISABLED)

    def _on_tree_double_click(self, _event=None) -> None:
        self._on_tree_select()
        sel = self.tree.selection()
        if not sel:
            return
        data = self._row_data.get(sel[0], {})
        messagebox.showinfo(
            data.get("item") or "Item",
            f"Status: {data.get('status', '-')}\n"
            f"What to do: {data.get('next_step', '-')}\n\n"
            f"What it does:\n{data.get('effect', '-')}\n\n"
            f"Repercussions:\n{data.get('repercussions', '-')}",
        )

    def _show_text_window(self, title: str, body: str, *, width: int = 640, height: int = 520) -> None:
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry(f"{width}x{height}")
        win.configure(bg=C["bg"])
        win.transient(self)
        txt = tk.Text(
            win,
            wrap=tk.WORD,
            bg=C["card"],
            fg=C["text"],
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            padx=14,
            pady=14,
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        txt.insert("1.0", body)
        txt.configure(state=tk.DISABLED)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 12))

    def _show_how(self) -> None:
        self._show_text_window("How this works", HOW_IT_WORKS)

    def _show_disclaimer(self) -> None:
        self._show_text_window("Disclaimer", DISCLAIMER_FULL, height=560)

    def _refresh_admin(self) -> None:
        if is_admin():
            self.admin_label.configure(text="Administrator: YES", style="AdminYes.TLabel")
        else:
            self.admin_label.configure(
                text="Administrator: NO  (elevate for full cleanup)",
                style="AdminNo.TLabel",
            )

    def _selected_modules(self) -> list[CleanModule]:
        return [m for m in self._modules if self._vars[m.id].get()]

    def _apply_profile(self, profile: str) -> None:
        predicate = PROFILE_IDS[profile]
        for mod in self._modules:
            self._vars[mod.id].set(bool(predicate(mod)))
        self._log(f"Preset applied: {profile}")
        self._on_selection_changed()

    def _set_all(self, value: bool) -> None:
        for var in self._vars.values():
            var.set(value)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        n = len(self._selected_modules())
        self.status_var.set(f"{n} module(s) selected")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in (self.scan_btn, self.dry_btn, self.clean_btn, self.elevate_btn):
            btn.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress_label.configure(text="Ready")

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._row_data.clear()

    def _insert_row(self, data: dict[str, str]) -> None:
        # Always store values in RESULT_COLUMNS order so displaycolumns can hide safely
        values = tuple(data.get(col, "") for col in RESULT_COLUMNS)
        iid = self.tree.insert("", tk.END, values=values)
        self._row_data[iid] = data

    def _fill_report(self, report: CleanReport, mode: str) -> None:
        self._last_report = report
        self._clear_tree()
        for result in report.results:
            if not result.items and not result.actions and not result.errors:
                continue
            if result.items:
                for item in result.items:
                    size = format_bytes(item.bytes_estimate) if item.bytes_estimate else "-"
                    self._insert_row(
                        {
                            "status": item.status or "-",
                            "next_step": item.next_step or "-",
                            "module": result.label,
                            "item": item.label,
                            "size": size,
                            "effect": item.effect or "-",
                            "repercussions": item.repercussions or "-",
                            "detail": item.detail,
                        }
                    )
            else:
                for action in result.actions[:20]:
                    self._insert_row(
                        {
                            "status": "-",
                            "next_step": "-",
                            "module": result.label,
                            "item": action,
                            "size": "-",
                            "effect": "-",
                            "repercussions": "-",
                            "detail": "",
                        }
                    )

            for err in result.errors[:10]:
                self._insert_row(
                    {
                        "status": "Error",
                        "next_step": "See Activity log / elevate if Access Denied",
                        "module": result.label,
                        "item": "ERROR",
                        "size": "-",
                        "effect": "-",
                        "repercussions": err,
                        "detail": "",
                    }
                )
                self._log(f"ERROR [{result.label}] {err}")

        for skipped in report.skipped_modules:
            self._insert_row(
                {
                    "status": "Needs Admin",
                    "next_step": "Restart as Administrator → Clean",
                    "module": "Skipped",
                    "item": skipped,
                    "size": "-",
                    "effect": "Module was not run",
                    "repercussions": "Restart as Administrator to include it",
                    "detail": "Needs Administrator",
                }
            )
            self._log(f"Skipped: {skipped}")

        if mode == "scan":
            self.summary_var.set(
                f"Found {report.item_count} item(s)  |  "
                f"Estimated reclaimable: {format_bytes(report.bytes_estimate)}  |  "
                f"Errors: {report.error_count}"
            )
        else:
            label = "Would free" if report.dry_run else "Freed"
            self.summary_var.set(
                f"{label}: {format_bytes(report.bytes_freed)}  |  "
                f"Actions: {report.action_count}  |  "
                f"Items: {report.item_count}  |  "
                f"Errors: {report.error_count}"
            )
            if not report.dry_run:
                self._log(
                    "Note: a new Scan may still list some items because "
                    "Windows recreates temp/browser/GPU caches, locked files remain, "
                    "or Admin was needed for system/privacy/service changes."
                )

    def _run_async(self, title: str, worker: Callable[[Callable[[str], None]], CleanReport], mode: str) -> None:
        if self._busy:
            return
        modules = self._selected_modules()
        if not modules:
            messagebox.showwarning(__app_name__, "Select at least one module.")
            return

        self._set_busy(True)
        self._log(f"--- {title} ({', '.join(m.id for m in modules)}) ---")
        self.status_var.set(title)

        def progress(msg: str) -> None:
            self._queue.put(("progress", msg))

        def target() -> None:
            try:
                report = worker(progress)
                self._queue.put(("done", mode, report))
            except Exception as e:
                self._queue.put(("error", str(e)))

        threading.Thread(target=target, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    text = msg[1]
                    self.progress_label.configure(text=text[:90])
                    self.status_var.set(text[:120])
                elif kind == "done":
                    _, mode, report = msg
                    self._fill_report(report, mode)
                    if mode == "clean" and not report.dry_run:
                        applied = report.action_count
                        failed = report.error_count
                        skipped = len(report.skipped_modules)
                        counts = getattr(report, "verify_counts", None) or {}
                        status_txt = (
                            ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "none"
                        )
                        fixed = counts.get("Fixed", 0)
                        not_fixed = counts.get("Not fixed", 0) + counts.get(
                            "Failed — Needs Admin", 0
                        )
                        still = counts.get("Still present", 0)
                        self.summary_var.set(
                            f"Clean + verify: Fixed {fixed}, Not fixed/Needs Admin {not_fixed}, "
                            f"Still present {still}. Actions ~{applied}, errors {failed}, "
                            f"admin-blocked modules {skipped}. Statuses — {status_txt}"
                        )
                        self._log(f"Verify counts: {status_txt}")
                        messagebox.showinfo(
                            __app_name__,
                            "Clean finished — Status is from a real re-check after Clean.\n\n"
                            f"Fixed (verified gone): {fixed}\n"
                            f"Not fixed / Needs Admin: {not_fixed}\n"
                            f"Still present (files locked/partial): {still}\n"
                            f"Actions: {applied} · Errors: {failed}\n\n"
                            "Status guide:\n"
                            "• Fixed — re-scan confirms it is gone\n"
                            "• Not fixed — still detected (elevate & Clean)\n"
                            "• Failed — Needs Admin — restart as Administrator, then Clean\n"
                            "• Still present — files remain; close apps / reboot / retry\n"
                            "• On next Scan: Came back = normal cache refill",
                        )
                    self._set_busy(False)
                    self.status_var.set("Done")
                    self._log(f"Finished ({mode}).")
                elif kind == "error":
                    self._set_busy(False)
                    self._log(f"Failed: {msg[1]}")
                    messagebox.showerror(__app_name__, msg[1])
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _on_scan(self) -> None:
        modules = self._selected_modules()

        def worker(progress: Callable[[str], None]) -> CleanReport:
            return Cleaner(modules).scan(progress)

        self._run_async("Scanning...", worker, "scan")

    def _on_clean(self, *, dry_run: bool) -> None:
        modules = self._selected_modules()
        if not modules:
            messagebox.showwarning(__app_name__, "Select at least one module.")
            return

        admin_ids = {
            "privacy",
            "telemetry_services",
            "caches",
            "logs",
            "bloatware",
            "bloatware_oem",
            "perf_services",
        }
        needs_admin = any(m.requires_admin for m in modules) or any(m.id in admin_ids for m in modules)
        if not dry_run and needs_admin and not is_admin():
            elevate = messagebox.askyesno(
                __app_name__,
                "Many selected items need Administrator or they will NOT stick "
                "and will show up again on the next Scan.\n\n"
                "Examples: privacy/AI policies, telemetry services, Windows Update cache, "
                "bloatware / OEM removal, optional performance services.\n\n"
                "Restart as Administrator now?\n\n"
                "Choose No to clean only what works without Admin (temps/browser caches).",
                icon=messagebox.WARNING,
            )
            if elevate:
                relaunch_as_admin()
                self.destroy()
                return

        aggressive = [m.label for m in modules if m.risk == Risk.AGGRESSIVE]
        if not dry_run:
            lines = [
                "DISCLAIMER — you use this tool at your own risk.",
                "No warranty. Not affiliated with Microsoft or any OEM.",
                "",
                "This will permanently delete files and/or change system settings.",
                "Prefer Scan → Dry-run first. Keep System Restore enabled when possible.",
                "",
                "Selected:",
                *[f"  - {m.label} [{m.risk.value}]" for m in modules],
            ]
            if aggressive:
                lines += [
                    "",
                    "Aggressive modules included (harder to undo):",
                    *[f"  - {n}" for n in aggressive],
                ]
            if needs_admin and not is_admin():
                lines += [
                    "",
                    "WARNING: Not Administrator - privacy/services/system caches will likely FAIL",
                    "and appear again on the next Scan.",
                ]
            lines += ["", "Continue and accept responsibility for these changes?"]
            if not messagebox.askyesno(__app_name__, "\n".join(lines), icon=messagebox.WARNING):
                return

        want_restore = (not dry_run) and bool(self.restore_var.get())

        def worker(progress: Callable[[str], None]) -> CleanReport:
            if want_restore:
                progress("Creating System Restore point...")
                from windowscleaner.utils.restore_point import create_restore_point

                ok, msg = create_restore_point("Windows Cleaner before clean")
                self._queue.put(("progress", msg))
                if not ok:
                    self._queue.put(("progress", f"Restore point skipped: {msg[:80]}"))
            return Cleaner(modules).clean(dry_run=dry_run, progress=progress)

        title = "Dry-run..." if dry_run else "Cleaning..."
        self._run_async(title, worker, "dry-run" if dry_run else "clean")

    def _on_elevate(self) -> None:
        if is_admin():
            messagebox.showinfo(__app_name__, "Already running as Administrator.")
            return
        if messagebox.askyesno(
            __app_name__,
            "Restart this app with Administrator rights?\n\n"
            "Needed for Windows Update cache, system logs, privacy/AI policies, "
            "telemetry services, bloatware / OEM removal, and optional performance services.",
        ):
            relaunch_as_admin()
            self.destroy()


def run_gui() -> int:
    app = WindowsCleanerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gui())
