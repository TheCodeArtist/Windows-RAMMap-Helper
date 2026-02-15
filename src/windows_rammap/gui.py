import os
import sys
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

    def __init__(self, parent):
        super().__init__(parent)

        # Title label
        self.title_label = ttk.Label(self, text="System Memory Breakdown:", font=("Segoe UI", 9, "bold"))
        self.title_label.pack(anchor="w", pady=(0, 4))

        # Progress bar canvas
        self.canvas = tk.Canvas(self, height=30, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(fill="x", pady=(0, 4))

        # Legend frame
        legend_frame = ttk.Frame(self)
        legend_frame.pack(anchor="w")

        # Color definitions matching Windows RAMMap
        self.colors = {
            "active": "#0078D4",      # Blue - Active memory
            "modified": "#FFA500",    # Orange - Modified pages
            "standby": "#90EE90",     # Light green - Standby list
            "free": "#E0E0E0"         # Light gray - Free memory
        }

        # Create legend items
        self.legend_labels = {}
        col = 0
        for name, color in self.colors.items():
            # Color box
            box = tk.Canvas(legend_frame, width=16, height=16, bg=color, highlightthickness=1, highlightbackground="#888888")
            box.grid(row=0, column=col, padx=(0 if col == 0 else 12, 4), pady=2)

            # Label
            label = ttk.Label(legend_frame, text=f"{name.capitalize()}: 0 MB (0%)")
            label.grid(row=0, column=col+1, pady=2)
            self.legend_labels[name] = label

            col += 2

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


class RamMapApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Windows RAMMap Helper")
        self.geometry("620x480")
        self.resizable(False, False)

        # Set window icon
        self._set_window_icon()

        # System tray setup
        self.tray_icon = None
        self.is_closing = False

        # Override window close behavior to hide to tray
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Hide window initially (will show after tray icon is created)
        self.withdraw()

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text="Windows Memory Maintenance",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            root,
            text="Trigger working set trimming and standby list purging on demand.",
        ).pack(anchor="w", pady=(4, 12))

        # Add memory progress bar
        self.progress_bar = MemoryProgressBar(root)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        controls = ttk.Frame(root)
        controls.pack(anchor="w", pady=(0, 10))

        self.trim_button = ttk.Button(
            controls, text="Trim All Working Sets", command=self.on_trim
        )
        self.trim_button.grid(row=0, column=0, padx=(0, 8))

        self.modified_button = ttk.Button(
            controls, text="Purge Modified List", command=self.on_purge_modified
        )
        self.modified_button.grid(row=0, column=1, padx=(0, 8))

        self.standby_button = ttk.Button(
            controls, text="Purge Standby List", command=self.on_purge_standby
        )
        self.standby_button.grid(row=0, column=2, padx=(0, 8))

        self.refresh_button = ttk.Button(
            controls, text="Refresh", command=self.refresh_memory_stats
        )
        self.refresh_button.grid(row=0, column=3)

        admin_status = is_admin()
        admin_text = "Yes" if admin_status else "No (run as Administrator recommended)"
        self.admin_label = ttk.Label(root, text=f"Administrator mode: {admin_text}")
        self.admin_label.pack(anchor="w", pady=(0, 8))

        self.log = tk.Text(root, height=10, wrap="word")
        self.log.pack(fill="both", expand=True)
        self._write_log("Application ready.")
        self._log_diagnostics(admin_status)

        # Initialize memory stats
        self.refresh_memory_stats()

        # Auto-refresh every 2 seconds
        self._schedule_auto_refresh()

        # Create system tray icon
        self.after(100, self._create_tray_icon)

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
        # Create a simple icon image
        icon_image = self._create_icon_image()

        # Create menu for the tray icon
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.MenuItem("Exit", self.quit_app)
        )

        # Create the tray icon
        self.tray_icon = pystray.Icon(
            "windows_rammap",
            icon_image,
            "Windows RAMMap Helper",
            menu
        )

        # Run the tray icon in a separate thread
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

        # Show the window after tray icon is created
        self.after(100, self.show_window)

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
