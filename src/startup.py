"""
Windows startup (auto-run) management via the registry.

Writes/removes a value under:
  HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

Using HKCU means no admin rights are required.
"""

import sys
import os

if sys.platform == 'win32':
    import winreg

REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TallyCounter"


def _get_launch_command() -> str:
    """Return the command that should be registered for auto-start."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller .exe — register the exe path directly.
        return f'"{sys.executable}"'
    else:
        # Running from source — use pythonw.exe (no console window) with the
        # absolute path to main.py.
        pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        if not os.path.exists(pythonw):
            pythonw = sys.executable  # fallback
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), 'main.py'))
        return f'"{pythonw}" "{main_py}"'


def is_startup_enabled() -> bool:
    """Return True if TallyCounter is registered to run at Windows startup."""
    if sys.platform != 'win32':
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_startup() -> None:
    """Register the app to start automatically with Windows."""
    if sys.platform != 'win32':
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
                        access=winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_launch_command())


def disable_startup() -> None:
    """Remove the app from Windows startup."""
    if sys.platform != 'win32':
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
                            access=winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass  # Already not registered
