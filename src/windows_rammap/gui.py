import json
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageDraw
import pystray

from .memory_ops import (
    check_privilege_status,
    get_memory_stats,
    is_admin,
    purge_modified_list,
    purge_standby_list,
    trim_all_working_sets,
)

STATUS_PRIVILEGE_NOT_HELD = 0xC0000061

# Debug mode flag - set to False to hide debug logs
DEBUG_MODE = False

_CONFIG_DIR_NAME = "WindowsRAMMapHelper"
_CONFIG_FILE_NAME = "config.json"

INTERVAL_OPTIONS = [
    ("5 min", 5),
    ("15 min", 15),
    ("30 min", 30),
    ("1 hour", 60),
    ("2 hours", 120),
    ("4 hours", 240),
    ("8 hours", 480),
]
INTERVAL_LABELS = [label for label, _ in INTERVAL_OPTIONS]
INTERVAL_BY_LABEL = {label: minutes for label, minutes in INTERVAL_OPTIONS}
LABEL_BY_INTERVAL = {minutes: label for label, minutes in INTERVAL_OPTIONS}
_DEFAULT_INTERVAL_MIN = 30


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not frozen, use the project root (3 levels up from this file)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    return os.path.join(base_path, relative_path)


class MemoryProgressBar(ttk.Frame):
    """Custom horizontal progress bar showing memory breakdown."""

    def __init__(self, parent, app=None):
        super().__init__(parent)

        # Store reference to main app for theme access
        self.app = app

        # Title label
        self.title_label = ttk.Label(self, text="System Memory Breakdown:", font=("Segoe UI", 9, "bold"))
        self.title_label.pack(anchor="w", pady=(0, 4))

        # Progress bar canvas
        self.canvas = tk.Canvas(self, height=30, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(fill="x", pady=(0, 4))

        # Color definitions matching Windows RAMMap
        self.colors = {
            "active": "#0078D4",      # Blue - Active memory
            "modified": "#FFA500",    # Orange - Modified pages
            "standby": "#90EE90",     # Light green - Standby list
            "free": "#E0E0E0"         # Light gray - Free memory
        }

        # Store legend frame reference (will be populated externally)
        self.legend_labels = {}

        # Info label for total
        self.total_label = ttk.Label(self, text="Total: 0 MB", font=("Segoe UI", 8))
        self.total_label.pack(anchor="w", pady=(4, 0))

        # Bind resize event to redraw
        self.canvas.bind("<Configure>", lambda e: self.update_display())

        # Store current stats
        self.current_stats = None

    def update_stats(self, stats):
        """Update the progress bar with new memory statistics."""
        self.current_stats = stats
        self.update_display()

    def update_display(self):
        """Redraw the progress bar based on current stats."""
        if not self.current_stats:
            return

        stats = self.current_stats

        # Clear canvas
        self.canvas.delete("all")

        # Get canvas dimensions
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        # If canvas not yet rendered, use requested width
        if width <= 1:
            width = 580
        if height <= 1:
            height = 30

        # Calculate percentages and widths
        total = stats.total
        if total == 0:
            return

        segments = [
            ("active", stats.active),
            ("modified", stats.modified),
            ("standby", stats.standby),
            ("free", stats.free)
        ]

        # Draw segments
        x = 0
        for name, value in segments:
            percentage = (value / total) * 100
            segment_width = int((value / total) * width)

            if segment_width > 0:
                self.canvas.create_rectangle(
                    x, 0, x + segment_width, height,
                    fill=self.colors[name],
                    outline=""
                )

                # Add text label if segment is wide enough
                if segment_width > 50:
                    text = f"{value} MB"
                    self.canvas.create_text(
                        x + segment_width // 2, height // 2,
                        text=text,
                        font=("Segoe UI", 8, "bold"),
                        fill="black" if name in ["standby", "free"] else "white"
                    )

                x += segment_width

            # Update legend
            self.legend_labels[name].config(
                text=f"{name.capitalize()}: {value} MB ({percentage:.1f}%)"
            )

        # Update total label
        self.total_label.config(text=f"Total Physical Memory: {total} MB")

    def update_theme(self, dark_mode):
        """Update canvas colors based on theme."""
        if dark_mode:
            self.canvas.config(bg="#1e1e1e", highlightbackground="#3c3c3c")
        else:
            self.canvas.config(bg="white", highlightbackground="#cccccc")
        self.update_display()


class RamMapApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Windows RAMMap Helper")

        # Window size calculations
        self.collapsed_height = 440
        self.expanded_height = 765

        self.geometry(f"520x{self.collapsed_height}")
        self.resizable(False, False)

        # Dark mode state
        self.dark_mode = False

        # Theme colors
        self.themes = {
            "light": {
                "bg": "#f0f0f0",
                "fg": "#000000",
                "canvas_bg": "white",
                "text_bg": "white",
                "text_fg": "#000000",
                "highlight": "#cccccc"
            },
            "dark": {
                "bg": "#2b2b2b",
                "fg": "#ffffff",
                "canvas_bg": "#1e1e1e",
                "text_bg": "#1e1e1e",
                "text_fg": "#d4d4d4",
                "highlight": "#3c3c3c"
            }
        }

        # Set window icon
        self._set_window_icon()

        # System tray setup
        self.tray_icon = None
        self.is_closing = False

        # Auto-purge state (loaded from config below)
        self._auto_purge_enabled = False
        self._auto_purge_interval_min = _DEFAULT_INTERVAL_MIN
        self._auto_purge_after_id = None
        self._countdown_after_id = None
        self._next_purge_time = None
        self._load_config()

        # Override window close behavior to hide to tray
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Hide window initially (will show after tray icon is created)
        self.withdraw()

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        # Store root frame reference for theming
        self.root_frame = root

        # Header with improved typography and dark mode toggle
        header_frame = ttk.Frame(root)
        header_frame.pack(fill="x", pady=(0, 2))

        ttk.Label(
            header_frame,
            text="Windows Memory Maintenance",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", anchor="w")

        # Dark mode toggle button in top-right
        self.theme_toggle_button = tk.Button(
            header_frame,
            text="Light Mode",
            command=self.toggle_theme,
            width=12,
            relief='raised',
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        self.theme_toggle_button.pack(side="right", anchor="e")

        ttk.Label(
            root,
            text="Trigger Working-set trimming and Standby-list purging on demand.",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 14))

        # Add memory progress bar
        self.progress_bar = MemoryProgressBar(root, app=self)
        self.progress_bar.pack(fill="x", pady=(0, 16))

        # Two-column layout: legend on left, buttons on right (centrally aligned)
        content_frame = ttk.Frame(root)
        content_frame.pack(pady=(0, 12))

        # Configure column weights for center alignment
        content_frame.columnconfigure(0, weight=1)  # Left padding - expandable
        content_frame.columnconfigure(1, weight=0)  # Legend column - fixed width
        content_frame.columnconfigure(2, weight=0)  # Separator column
        content_frame.columnconfigure(3, weight=0)  # Button column - fixed width
        content_frame.columnconfigure(4, weight=1)  # Right padding - expandable

        # Left column: Memory legend with grouped frame
        legend_container = ttk.LabelFrame(content_frame, text="Memory Details", padding=(12, 8), relief="flat", borderwidth=0)
        legend_container.grid(row=0, column=1, sticky="n", padx=(0, 0))

        self.legend_frame = ttk.Frame(legend_container)
        self.legend_frame.pack(fill="both", expand=True)

        # Create legend items in the left column
        self._create_legend()

        # Vertical separator between columns
        separator = ttk.Separator(content_frame, orient="vertical")
        separator.grid(row=0, column=2, sticky="ns", padx=16)

        # Right column: Action buttons with grouped frame
        button_container = ttk.LabelFrame(content_frame, text="Memory Operations", padding=(12, 8), relief="flat", borderwidth=0)
        button_container.grid(row=0, column=3, sticky="n", padx=(0, 0))

        # Button styling
        button_width = 24  # Slightly wider for better proportions
        button_pady = 8    # Consistent spacing between buttons

        # Use tk.Button instead of ttk.Button for proper color control in dark mode
        self.trim_button = tk.Button(
            button_container, text="Trim All Working Sets", width=button_width, command=self.on_trim,
            relief='raised', borderwidth=1, font=("Segoe UI", 9)
        )
        self.trim_button.grid(row=0, column=0, pady=(0, button_pady), sticky="ew")

        self.modified_button = tk.Button(
            button_container, text="Purge Modified List", width=button_width, command=self.on_purge_modified,
            relief='raised', borderwidth=1, font=("Segoe UI", 9)
        )
        self.modified_button.grid(row=1, column=0, pady=(0, button_pady), sticky="ew")

        self.standby_button = tk.Button(
            button_container, text="Purge Standby List", width=button_width, command=self.on_purge_standby,
            relief='raised', borderwidth=1, font=("Segoe UI", 9)
        )
        self.standby_button.grid(row=2, column=0, pady=(0, button_pady), sticky="ew")

        self.refresh_button = tk.Button(
            button_container, text="Refresh", width=button_width, command=self.refresh_memory_stats,
            relief='raised', borderwidth=1, font=("Segoe UI", 9)
        )
        self.refresh_button.grid(row=3, column=0, sticky="ew")

        # --- Auto-purge controls (compact row below the two columns) ---
        auto_purge_frame = ttk.Frame(root)
        auto_purge_frame.pack(pady=(0, 0))

        self._auto_purge_var = tk.BooleanVar(value=self._auto_purge_enabled)
        self.auto_purge_checkbox = tk.Checkbutton(
            auto_purge_frame,
            text="Auto-purge standby",
            variable=self._auto_purge_var,
            command=self._on_auto_purge_checkbox_changed,
            font=("Segoe UI", 9),
        )
        self.auto_purge_checkbox.pack(side="left")

        ttk.Label(auto_purge_frame, text="Every:", font=("Segoe UI", 9)).pack(
            side="left", padx=(12, 6),
        )
        self.interval_combobox = ttk.Combobox(
            auto_purge_frame,
            values=INTERVAL_LABELS,
            state="readonly",
            width=10,
            font=("Segoe UI", 9),
        )
        self.interval_combobox.set(
            LABEL_BY_INTERVAL.get(self._auto_purge_interval_min, "30 min")
        )
        self.interval_combobox.pack(side="left")
        self.interval_combobox.bind("<<ComboboxSelected>>", self._on_interval_changed)

        ttk.Style().configure(
            'Countdown.TLabel', foreground='#888888', font=("Segoe UI", 8),
        )
        self.countdown_label = ttk.Label(
            auto_purge_frame, text="", style='Countdown.TLabel',
        )
        self.countdown_label.pack(side="left", padx=(12, 0))

        # Administrator status with better styling
        admin_status = is_admin()
        admin_text = "Yes" if admin_status else "No (run as Administrator recommended)"
        self.admin_label = ttk.Label(root, text=f"Administrator mode: {admin_text}",
                                    font=("Segoe UI", 9))
        self.admin_label.pack(anchor="w", pady=(12, 10))

        # Expandable logs section
        logs_container = ttk.Frame(root)
        logs_container.pack(fill="x", expand=False, pady=(0, 0))

        # Logs header with toggle button
        logs_header = ttk.Frame(logs_container)
        logs_header.pack(fill="x", pady=(0, 0))

        self.logs_expanded = False
        self.logs_toggle_button = tk.Button(
            logs_header,
            text="▶ Show Logs",
            command=self.toggle_logs,
            width=15,
            relief='raised',
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        self.logs_toggle_button.pack(side="left", anchor="w")

        # Logs content (initially hidden)
        self.logs_content = ttk.Frame(logs_container)

        # Create scrollbar for logs
        logs_scrollbar = ttk.Scrollbar(self.logs_content)
        logs_scrollbar.pack(side="right", fill="y")

        self.log = tk.Text(self.logs_content, height=20, wrap="word", yscrollcommand=logs_scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True, pady=(4, 0))

        # Connect scrollbar to text widget
        logs_scrollbar.config(command=self.log.yview)

        self._write_log("Application ready.")
        self._log_diagnostics(admin_status)

        # Initialize memory stats
        self.refresh_memory_stats()

        # Auto-refresh every 2 seconds
        self._schedule_auto_refresh()

        # Create system tray icon
        self.after(100, self._create_tray_icon)

        # Start auto-purge if enabled from saved config
        if self._auto_purge_enabled:
            self._start_auto_purge()
        self._update_countdown_display()

    def _create_legend(self) -> None:
        """Create the memory legend items in the right column."""
        # Configure grid for proper alignment
        self.legend_frame.columnconfigure(0, weight=0)  # Color box column
        self.legend_frame.columnconfigure(1, weight=1)  # Label column - expandable

        # Store legend canvas boxes for theme updates
        self.legend_boxes = {}

        row = 0
        legend_pady = 6  # Vertical spacing between legend items

        for name, color in self.progress_bar.colors.items():
            # Color box with better styling
            box = tk.Canvas(self.legend_frame, width=18, height=18, bg=color,
                          highlightthickness=1, highlightbackground="#666666")
            box.grid(row=row, column=0, padx=(0, 8), pady=(0, legend_pady if row < 3 else 0), sticky="w")
            self.legend_boxes[name] = box

            # Label with improved font
            label = ttk.Label(self.legend_frame, text=f"{name.capitalize()}: 0 MB (0%)",
                            font=("Segoe UI", 9))
            label.grid(row=row, column=1, pady=(0, legend_pady if row < 3 else 0), sticky="w")
            self.progress_bar.legend_labels[name] = label

            row += 1

    def toggle_logs(self) -> None:
        """Toggle the visibility of the logs section."""
        if self.logs_expanded:
            # Collapse logs
            self.logs_content.pack_forget()
            self.logs_toggle_button.config(text="▶ Show Logs")
            self.logs_expanded = False
            # Resize window to collapsed height
            self.geometry(f"520x{self.collapsed_height}")
        else:
            # Expand logs
            self.logs_content.pack(fill="both", expand=True, pady=(4, 0))
            self.logs_toggle_button.config(text="▼ Hide Logs")
            self.logs_expanded = True
            # Resize window to expanded height
            self.geometry(f"520x{self.expanded_height}")

    def _write_log(self, message: str) -> None:
        # Filter debug messages when DEBUG_MODE is False
        if not DEBUG_MODE and "[Debug]" in message:
            return
        self.log.insert("end", f"{message}\n")
        self.log.see("end")

    def refresh_memory_stats(self) -> None:
        """Refresh the memory statistics display."""
        try:
            stats = get_memory_stats()
            self.progress_bar.update_stats(stats)
        except Exception as e:
            self._write_log(f"Error refreshing memory stats: {e}")

    def _schedule_auto_refresh(self) -> None:
        """Schedule automatic refresh of memory stats every 2 seconds."""
        self.refresh_memory_stats()
        self.after(2000, self._schedule_auto_refresh)

    def _log_diagnostics(self, admin_status: bool) -> None:
        self._write_log(f"[Diagnostics] Administrator mode: {'Yes' if admin_status else 'No'}")

        priv_status, error_detail = check_privilege_status("SeProfileSingleProcessPrivilege")
        self._write_log(f"[Diagnostics] SeProfileSingleProcessPrivilege: {priv_status}")

        if error_detail:
            self._write_log(f"[Debug] Error detail: {error_detail}")

        if priv_status == "missing":
            self._write_log(
                "[Warning] SeProfileSingleProcessPrivilege is not in the token. "
                "Purge Standby List will fail."
            )
        elif priv_status == "available":
            self._write_log(
                "[Info] SeProfileSingleProcessPrivilege is available and will be enabled on demand."
            )
        elif priv_status == "error":
            self._write_log(
                "[Error] Could not check privilege status."
            )

    # --- Config persistence ---------------------------------------------------

    @staticmethod
    def _get_config_path() -> str:
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, _CONFIG_DIR_NAME, _CONFIG_FILE_NAME)

    def _load_config(self) -> None:
        try:
            path = self._get_config_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._auto_purge_enabled = bool(data.get("auto_purge_enabled", False))
                interval = int(data.get("auto_purge_interval_minutes", _DEFAULT_INTERVAL_MIN))
                if interval in LABEL_BY_INTERVAL:
                    self._auto_purge_interval_min = interval
        except Exception:
            pass

    def _save_config(self) -> None:
        try:
            path = self._get_config_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "auto_purge_enabled": self._auto_purge_enabled,
                "auto_purge_interval_minutes": self._auto_purge_interval_min,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._write_log(f"[Warning] Could not save config: {e}")

    # --- Auto-purge timer -----------------------------------------------------

    def _start_auto_purge(self) -> None:
        self._stop_auto_purge()
        self._auto_purge_enabled = True
        interval_s = self._auto_purge_interval_min * 60
        self._next_purge_time = time.time() + interval_s
        self._auto_purge_after_id = self.after(interval_s * 1000, self._on_auto_purge_tick)

    def _stop_auto_purge(self) -> None:
        if self._auto_purge_after_id is not None:
            self.after_cancel(self._auto_purge_after_id)
            self._auto_purge_after_id = None
        self._next_purge_time = None

    def _on_auto_purge_tick(self) -> None:
        self._write_log("[Auto-purge] Purging standby list...")

        def task() -> None:
            status = purge_standby_list()
            if status == 0:
                self.after(0, self._write_log, "[Auto-purge] Standby list purged successfully.")
                self.after(0, self.refresh_memory_stats)
            else:
                hex_status = f"0x{status & 0xFFFFFFFF:08X}"
                self.after(0, self._write_log, f"[Auto-purge] Purge failed. NTSTATUS: {hex_status}")

        self._run_in_background(task)

        if self._auto_purge_enabled:
            interval_s = self._auto_purge_interval_min * 60
            self._next_purge_time = time.time() + interval_s
            self._auto_purge_after_id = self.after(interval_s * 1000, self._on_auto_purge_tick)

    def _reset_auto_purge_timer(self) -> None:
        if self._auto_purge_enabled:
            self._start_auto_purge()

    # --- Countdown display ----------------------------------------------------

    def _update_countdown_display(self) -> None:
        if self._auto_purge_enabled and self._next_purge_time is not None:
            remaining = max(0, self._next_purge_time - time.time())
            minutes, seconds = divmod(int(remaining), 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                countdown = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                countdown = f"{minutes}:{seconds:02d}"
            self.countdown_label.config(text=f"Next in {countdown}")
            self._update_tray_tooltip(countdown)
        else:
            self.countdown_label.config(text="")
            self._update_tray_tooltip(None)
        self._countdown_after_id = self.after(1000, self._update_countdown_display)

    def _update_tray_tooltip(self, countdown: str | None) -> None:
        if self.tray_icon is None:
            return
        base = "Windows RAMMap Helper"
        if countdown:
            self.tray_icon.title = f"{base}\nAuto-purge in {countdown}"
        else:
            self.tray_icon.title = base

    # --- Auto-purge toggle handlers -------------------------------------------

    def _on_auto_purge_checkbox_changed(self) -> None:
        enabled = self._auto_purge_var.get()
        self._auto_purge_enabled = enabled
        if enabled:
            self._start_auto_purge()
            interval_text = LABEL_BY_INTERVAL.get(self._auto_purge_interval_min, "?")
            self._write_log(f"Auto-purge enabled (every {interval_text}).")
        else:
            self._stop_auto_purge()
            self._write_log("Auto-purge disabled.")
        self._save_config()

    def _on_interval_changed(self, event=None) -> None:
        label = self.interval_combobox.get()
        minutes = INTERVAL_BY_LABEL.get(label)
        if minutes is None:
            return
        self._auto_purge_interval_min = minutes
        if self._auto_purge_enabled:
            self._start_auto_purge()
            self._write_log(f"Auto-purge interval changed to {label}.")
        self._save_config()
        self._rebuild_tray_menu()

    def _toggle_auto_purge_from_tray(self, icon=None, item=None) -> None:
        """Called from pystray thread -- flip the flag immediately for the
        checked callback, then schedule UI/timer work on the main thread."""
        self._auto_purge_enabled = not self._auto_purge_enabled
        self.after(0, self._apply_auto_purge_state_from_tray)

    def _apply_auto_purge_state_from_tray(self) -> None:
        self._auto_purge_var.set(self._auto_purge_enabled)
        if self._auto_purge_enabled:
            self._start_auto_purge()
            interval_text = LABEL_BY_INTERVAL.get(self._auto_purge_interval_min, "?")
            self._write_log(f"Auto-purge enabled from tray (every {interval_text}).")
        else:
            self._stop_auto_purge()
            self._write_log("Auto-purge disabled from tray.")
        self._save_config()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.trim_button.config(state=state)
        self.modified_button.config(state=state)
        self.standby_button.config(state=state)
        self.refresh_button.config(state=state)

    def _run_in_background(self, fn) -> None:
        def runner() -> None:
            self.after(0, self._set_busy, True)
            try:
                fn()
            finally:
                self.after(0, self._set_busy, False)

        threading.Thread(target=runner, daemon=True).start()

    def on_trim(self) -> None:
        self._write_log("Starting working set trim...")

        def task() -> None:
            result = trim_all_working_sets()
            msg = f"Working set trim complete. Success: {result.success_count}, Failed: {result.failed_count}"
            self.after(0, self._write_log, msg)
            self.after(0, self.refresh_memory_stats)

        self._run_in_background(task)

    def on_purge_standby(self) -> None:
        self._write_log("Purging standby list...")

        def task() -> None:
            status = purge_standby_list()
            if status == 0:
                self.after(0, self._write_log, "Standby list purged successfully.")
                self.after(0, self.refresh_memory_stats)
                self.after(0, self._reset_auto_purge_timer)
                return

            hex_status = f"0x{status & 0xFFFFFFFF:08X}"
            is_priv_error = (status & 0xFFFFFFFF) == STATUS_PRIVILEGE_NOT_HELD

            if is_priv_error:
                details = (
                    f"NtSetSystemInformation failed with NTSTATUS {hex_status} "
                    "(STATUS_PRIVILEGE_NOT_HELD).\n"
                    "The process token is missing SeProfileSingleProcessPrivilege.\n"
                    "Launch from an elevated Administrator shell/UAC and try again."
                )
            else:
                details = (
                    f"NtSetSystemInformation failed with NTSTATUS {hex_status}.\n"
                    "Run the app as Administrator."
                )

            self.after(0, self._write_log, f"Standby list purge failed. NTSTATUS: {hex_status}")
            self.after(0, messagebox.showwarning, "Standby Purge Failed", details)

        self._run_in_background(task)

    def on_purge_modified(self) -> None:
        self._write_log("Purging modified list...")

        def task() -> None:
            status = purge_modified_list()
            if status == 0:
                self.after(0, self._write_log, "Modified list purged successfully.")
                self.after(0, self.refresh_memory_stats)
                return

            hex_status = f"0x{status & 0xFFFFFFFF:08X}"
            is_priv_error = (status & 0xFFFFFFFF) == STATUS_PRIVILEGE_NOT_HELD

            if is_priv_error:
                details = (
                    f"NtSetSystemInformation failed with NTSTATUS {hex_status} "
                    "(STATUS_PRIVILEGE_NOT_HELD).\n"
                    "The process token is missing SeProfileSingleProcessPrivilege.\n"
                    "Launch from an elevated Administrator shell/UAC and try again."
                )
            else:
                details = (
                    f"NtSetSystemInformation failed with NTSTATUS {hex_status}.\n"
                    "Run the app as Administrator."
                )

            self.after(0, self._write_log, f"Modified list purge failed. NTSTATUS: {hex_status}")
            self.after(0, messagebox.showwarning, "Modified Purge Failed", details)

        self._run_in_background(task)

    def _set_window_icon(self) -> None:
        """Set the window icon to match the executable icon."""
        icon_path = get_resource_path('rammap.ico')

        try:
            # On Windows, set the icon using iconbitmap
            if os.name == 'nt' and os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            # Silently fail if icon cannot be set
            pass

    def _create_tray_icon(self) -> None:
        """Create the system tray icon with menu."""
        icon_image = self._create_icon_image()

        self.tray_icon = pystray.Icon(
            "windows_rammap",
            icon_image,
            "Windows RAMMap Helper",
            self._build_tray_menu(),
        )

        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.after(100, self.show_window)

    def _build_tray_menu(self) -> pystray.Menu:
        def auto_purge_label(item):
            interval = LABEL_BY_INTERVAL.get(self._auto_purge_interval_min, "?")
            return f"Auto-purge (every {interval})"

        return pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                auto_purge_label,
                self._toggle_auto_purge_from_tray,
                checked=lambda item: self._auto_purge_enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app),
        )

    def _rebuild_tray_menu(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.menu = self._build_tray_menu()
            self.tray_icon.update_menu()

    def _create_icon_image(self) -> Image.Image:
        """Load the application icon for the system tray."""
        # Try to load the icon file from the project root
        icon_path = get_resource_path('rammap.ico')

        try:
            # Load the icon file
            image = Image.open(icon_path)
            return image
        except Exception as e:
            self._write_log(f"[Warning] Could not load icon file: {e}. Using fallback icon.")

            # Fallback: Create a simple icon image
            width = 64
            height = 64
            image = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(image)

            # Draw a blue circle (memory theme)
            draw.ellipse([8, 8, 56, 56], fill='#0078D4', outline='#005A9E', width=2)

            # Draw inner circle for RAM chip representation
            draw.ellipse([20, 20, 44, 44], fill='white', outline='#0078D4', width=2)

            return image

    def _disable_minimize_button(self) -> None:
        """Disable the minimize button on Windows."""
        try:
            import ctypes
            from ctypes import wintypes

            # Update the window to ensure it's fully created
            self.update_idletasks()

            # Get window handle - winfo_id() returns HWND on Windows
            hwnd = self.winfo_id()
            if not hwnd:
                self._write_log("[Debug] Failed to get window handle")
                return

            self._write_log(f"[Debug] Initial HWND: 0x{hwnd:08X}")

            # Get the actual top-level window (the one with the title bar)
            # Sometimes tkinter returns a child window, we need the parent
            GetParent = ctypes.windll.user32.GetParent
            GetParent.restype = wintypes.HWND
            GetParent.argtypes = [wintypes.HWND]

            parent_hwnd = GetParent(hwnd)
            if parent_hwnd:
                self._write_log(f"[Debug] Parent HWND: 0x{parent_hwnd:08X}")
                hwnd = parent_hwnd
            else:
                # If no parent, hwnd is already the top-level window
                self._write_log(f"[Debug] No parent, using HWND: 0x{hwnd:08X}")

            # Define Windows constants
            GWL_STYLE = -16
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000

            # Define functions with proper signatures
            GetWindowLongW = ctypes.windll.user32.GetWindowLongW
            GetWindowLongW.restype = wintypes.LONG
            GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

            SetWindowLongW = ctypes.windll.user32.SetWindowLongW
            SetWindowLongW.restype = wintypes.LONG
            SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]

            SetWindowPos = ctypes.windll.user32.SetWindowPos
            SetWindowPos.restype = wintypes.BOOL
            SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

            # Get current window style
            style = GetWindowLongW(hwnd, GWL_STYLE)
            self._write_log(f"[Debug] Current style: 0x{style:08X}")

            # Check if minimize box is present
            has_minimize = (style & WS_MINIMIZEBOX) != 0
            has_maximize = (style & WS_MAXIMIZEBOX) != 0
            self._write_log(f"[Debug] Has minimize box: {has_minimize}, Has maximize box: {has_maximize}")

            if not has_minimize and not has_maximize:
                self._write_log("[Debug] Warning: Neither minimize nor maximize box found in style!")
                return

            # Remove minimize and maximize box styles
            new_style = style & ~WS_MINIMIZEBOX & ~WS_MAXIMIZEBOX
            self._write_log(f"[Debug] New style: 0x{new_style:08X}")

            # Set new window style
            result = SetWindowLongW(hwnd, GWL_STYLE, new_style)
            self._write_log(f"[Debug] SetWindowLong result: 0x{result:08X}")

            # Force window to redraw
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            pos_result = SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
            self._write_log(f"[Debug] SetWindowPos result: {pos_result}")

            # Verify the style was changed
            verify_style = GetWindowLongW(hwnd, GWL_STYLE)
            self._write_log(f"[Debug] Verified style: 0x{verify_style:08X}")

            if verify_style == new_style:
                self._write_log("[Debug] Minimize button disabled successfully")
            else:
                self._write_log("[Debug] Style change may not have applied correctly")

        except Exception as e:
            import traceback
            self._write_log(f"[Debug] Failed to disable minimize button: {e}")
            self._write_log(f"[Debug] Traceback: {traceback.format_exc()}")

    def on_window_close(self) -> None:
        """Handle window close button - hide to tray instead of closing."""
        self.withdraw()

    def show_window(self, icon=None, item=None) -> None:
        """Show the main window."""
        self.after(0, self._show_window_internal)

    def _show_window_internal(self) -> None:
        """Internal method to show window (must be called from main thread)."""
        self.deiconify()
        self.lift()
        self.focus_force()

        # Disable minimize button after window is shown (Windows only)
        if os.name == 'nt':
            self.after(50, self._disable_minimize_button)

    def quit_app(self, icon=None, item=None) -> None:
        """Quit the application completely."""
        self.is_closing = True

        # Stop the tray icon
        if self.tray_icon:
            self.tray_icon.stop()

        # Destroy the window
        self.after(0, self.destroy)

    def toggle_theme(self) -> None:
        """Toggle between dark mode and light mode."""
        self.dark_mode = not self.dark_mode
        theme = self.themes["dark"] if self.dark_mode else self.themes["light"]

        # Update button text
        if self.dark_mode:
            self.theme_toggle_button.config(text=" Dark Mode")
        else:
            self.theme_toggle_button.config(text="Light Mode")

        # Update main window background
        self.config(bg=theme["bg"])

        # Update text widget (logs)
        self.log.config(bg=theme["text_bg"], fg=theme["text_fg"],
                       insertbackground=theme["text_fg"])

        # Update progress bar canvas
        self.progress_bar.update_theme(self.dark_mode)

        # Update legend boxes border
        for name, box in self.legend_boxes.items():
            if self.dark_mode:
                box.config(highlightbackground="#555555")
            else:
                box.config(highlightbackground="#666666")

        # Apply ttk style for dark/light mode without changing theme
        # This prevents layout shifts by only updating colors, not the base theme
        style = ttk.Style()
        if self.dark_mode:
            # Dark mode colors - light text on dark background for readability
            style.configure('TFrame', background='#2b2b2b')
            style.configure('TLabel', background='#2b2b2b', foreground='#e0e0e0')
            style.configure('TLabelframe', background='#2b2b2b', foreground='#e0e0e0',
                          borderwidth=0, relief='flat')
            style.configure('TLabelframe.Label', background='#2b2b2b', foreground='#e0e0e0')

            # Button styling with explicit dark background
            style.configure('TButton',
                          background='#404040',
                          foreground='#ffffff',
                          borderwidth=1,
                          focuscolor='#505050',
                          darkcolor='#2b2b2b',
                          lightcolor='#555555',
                          relief='raised')
            style.map('TButton',
                     background=[('disabled', '#2b2b2b'), ('active', '#505050'), ('pressed', '#303030')],
                     foreground=[('disabled', '#666666'), ('active', '#ffffff'), ('pressed', '#ffffff')],
                     bordercolor=[('active', '#606060')])
            style.configure('TSeparator', background='#3c3c3c')
            style.configure('TCombobox',
                          fieldbackground='#404040', background='#404040',
                          foreground='#e0e0e0', arrowcolor='#e0e0e0')
            style.map('TCombobox',
                     fieldbackground=[('readonly', '#404040')],
                     foreground=[('readonly', '#e0e0e0')])
            style.configure('Countdown.TLabel', background='#2b2b2b', foreground='#999999')
        else:
            # Light mode colors - dark text on light background for readability
            style.configure('TFrame', background='#f0f0f0')
            style.configure('TLabel', background='#f0f0f0', foreground='#000000')
            style.configure('TLabelframe', background='#f0f0f0', foreground='#000000',
                          borderwidth=0, relief='flat')
            style.configure('TLabelframe.Label', background='#f0f0f0', foreground='#000000')

            # Button styling with explicit light background
            style.configure('TButton',
                          background='#e1e1e1',
                          foreground='#000000',
                          borderwidth=1,
                          relief='raised')
            style.map('TButton',
                     background=[('disabled', '#f0f0f0'), ('active', '#e5f1fb'), ('pressed', '#cce4f7')],
                     foreground=[('disabled', '#a0a0a0'), ('active', '#000000'), ('pressed', '#000000')])
            style.configure('TSeparator', background='#d9d9d9')
            style.configure('TCombobox',
                          fieldbackground='white', background='#e1e1e1',
                          foreground='#000000', arrowcolor='#000000')
            style.map('TCombobox',
                     fieldbackground=[('readonly', 'white')],
                     foreground=[('readonly', '#000000')])
            style.configure('Countdown.TLabel', background='#f0f0f0', foreground='#888888')

        # Force update of all widgets to apply new styles immediately
        self.update_idletasks()

        # Directly set tk.Button colors for guaranteed dark mode support
        if self.dark_mode:
            # Dark mode: dark background, light text for all buttons
            button_bg = '#404040'
            button_fg = '#ffffff'
            button_active_bg = '#505050'
            button_active_fg = '#ffffff'
        else:
            # Light mode: light background, dark text for all buttons
            button_bg = '#f0f0f0'
            button_fg = '#000000'
            button_active_bg = '#e5f1fb'
            button_active_fg = '#000000'

        # Apply colors to all tk.Buttons
        for btn in [self.trim_button, self.modified_button, self.standby_button,
                   self.refresh_button, self.logs_toggle_button, self.theme_toggle_button]:
            btn.config(bg=button_bg, fg=button_fg,
                      activebackground=button_active_bg, activeforeground=button_active_fg)

        self.auto_purge_checkbox.config(
            bg=button_bg, fg=button_fg,
            activebackground=button_active_bg, activeforeground=button_active_fg,
            selectcolor=button_bg,
        )

        self._write_log(f"Theme switched to {'dark' if self.dark_mode else 'light'} mode.")
