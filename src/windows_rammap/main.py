import ctypes
import os
import subprocess
import sys
from tkinter import messagebox


def main() -> None:
    # Check for single instance before elevating
    if not _check_single_instance():
        messagebox.showwarning(
            "Already Running",
            "Windows RAMMap Helper is already running.\n\n"
            "Please check the system tray or task manager."
        )
        raise SystemExit(0)

    _request_admin_on_windows()
    # Import GUI components only when needed
    from .gui import RamMapApp
    app = RamMapApp()
    app.mainloop()


def _check_single_instance() -> bool:
    """
    Check if another instance is already running using a Windows mutex.
    Returns True if this is the only instance, False if another is running.
    """
    if os.name != "nt":
        return True  # Only enforce on Windows

    from ctypes import wintypes

    # Define Windows API functions
    kernel32 = ctypes.windll.kernel32

    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    CreateMutexW.restype = wintypes.HANDLE

    GetLastError = kernel32.GetLastError
    GetLastError.restype = wintypes.DWORD

    # Create a uniquely named mutex for this application
    mutex_name = "Global\\WindowsRAMMapHelper_SingleInstance_Mutex"
    ERROR_ALREADY_EXISTS = 183

    # Try to create the mutex
    mutex_handle = CreateMutexW(None, False, mutex_name)

    if mutex_handle:
        error = GetLastError()
        if error == ERROR_ALREADY_EXISTS:
            # Another instance is already running
            return False
        # Successfully created new mutex - this is the first instance
        # Note: We intentionally don't close the mutex so it persists
        # until the process exits
        return True

    # Failed to create mutex (shouldn't happen normally)
    return True


def _request_admin_on_windows() -> None:
    if os.name != "nt":
        return

    # Import only when needed
    from .memory_ops import is_admin

    if is_admin():
        return

    # Use sys.executable for both frozen and regular Python
    executable = sys.executable
    params = subprocess.list2cmdline(sys.argv if not getattr(sys, "frozen", False) else sys.argv[1:])

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)

    # If elevation was launched successfully, exit this process
    if int(result) > 32:
        raise SystemExit(0)
