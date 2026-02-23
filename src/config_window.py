import os
import sys
import winreg
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QLineEdit, QPushButton, QListWidget,
                              QListWidgetItem, QFileDialog, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from database import Database

WINDOW_STYLE = """
    QWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QLineEdit {
        background-color: #252525;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 10px;
        color: #e0e0e0;
        font-size: 13px;
    }
    QLineEdit:focus { border: 1px solid #4ade80; }
    QLineEdit:disabled { color: #555; background-color: #1e1e1e; }
    QListWidget {
        background-color: #252525;
        border: 1px solid #333;
        border-radius: 6px;
        outline: none;
    }
    QListWidget::item {
        padding: 8px 12px;
        border-bottom: 1px solid #2a2a2a;
    }
    QListWidget::item:selected {
        background-color: #2d4a35;
        color: #4ade80;
    }
    QListWidget::item:hover:!selected { background-color: #2a2a2a; }
    QListWidget:disabled { background-color: #1e1e1e; border-color: #2a2a2a; }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 7px 18px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #3a3a3a; border: 1px solid #666; }
    QPushButton#saveBtn {
        background-color: #1a3a24;
        border: 1px solid #4ade80;
        color: #4ade80;
        font-weight: bold;
    }
    QPushButton#saveBtn:hover { background-color: #22502e; }
    QPushButton:disabled { color: #555; border-color: #333; background-color: #222; }
    QLabel#sectionLabel { color: #888; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
    QLabel#statusLabel { color: #666; font-size: 12px; padding: 4px 0; }
"""

# ── Registry enumeration ───────────────────────────────────────────────────────

UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _exe_from_icon(display_icon):
    # type: (str) -> str
    """Extract exe path from a DisplayIcon value like 'C:\\app.exe,0'."""
    if not display_icon:
        return ""
    path = display_icon.strip().strip('"')
    if "," in path:
        path = path.rsplit(",", 1)[0].strip().strip('"')
    if path.lower().endswith(".exe") and os.path.isfile(path):
        return path
    return ""


def _exe_from_location(install_location):
    # type: (str) -> str
    """Find a single .exe in the root of the install folder."""
    loc = install_location.strip().strip('"')
    if not loc or not os.path.isdir(loc):
        return ""
    try:
        exes = [f for f in os.listdir(loc) if f.lower().endswith(".exe")]
        if len(exes) == 1:
            return os.path.join(loc, exes[0])
    except OSError:
        pass
    return ""


def enumerate_installed_apps():
    # type: () -> List[Tuple[str, str]]
    """
    Return a sorted list of (display_name, exe_path) for installed apps.
    exe_path may be an empty string if it could not be resolved — those apps
    are still included so the user can find them and use Browse to locate the exe.
    """
    apps = {}  # type: dict

    for hive, key_path in UNINSTALL_KEYS:
        try:
            root = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(root, i)
                    i += 1
                except OSError:
                    break
                try:
                    sub = winreg.OpenKey(root, sub_name)
                except OSError:
                    continue
                with sub:
                    def _val(k):
                        try:
                            return str(winreg.QueryValueEx(sub, k)[0])
                        except OSError:
                            return ""

                    name     = _val("DisplayName").strip()
                    icon     = _val("DisplayIcon")
                    location = _val("InstallLocation")
                    sysc     = _val("SystemComponent")
                    noremove = _val("NoRemove")

                    if not name:
                        continue
                    if sysc == "1":
                        continue      # Windows components
                    if noremove == "1" and not icon:
                        continue      # Silent system entries

                    exe = _exe_from_icon(icon) or _exe_from_location(location)

                    # Keep only the first (best) entry per name
                    if name not in apps or (not apps[name] and exe):
                        apps[name] = exe

    return sorted(apps.items(), key=lambda x: x[0].lower())


# ── Background loader thread ───────────────────────────────────────────────────

class AppLoaderThread(QThread):
    apps_loaded = pyqtSignal(list)

    def run(self):
        self.apps_loaded.emit(enumerate_installed_apps())


# ── Config window ──────────────────────────────────────────────────────────────

class ConfigWindow(QWidget):
    configuration_saved = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.db = Database()
        self._all_apps = []  # type: List[Tuple[str, str]]
        self._selected_exe = ""
        self._locked = False
        self.init_ui()
        self.check_initial_config()

    def init_ui(self):
        self.setWindowTitle("Tally Counter — Configure")
        self.setMinimumSize(520, 580)
        self.setStyleSheet(WINDOW_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(8)

        # Header
        lbl = QLabel("SELECT APP TO MONITOR")
        lbl.setObjectName("sectionLabel")
        root.addWidget(lbl)

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search installed apps…")
        self.search_edit.textChanged.connect(self._filter_list)
        root.addWidget(self.search_edit)

        # Status label (loading / count)
        self.status_label = QLabel("Loading installed apps…")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        # App list
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(300)
        self.app_list.currentItemChanged.connect(self._on_selection_changed)
        self.app_list.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self.app_list)

        # Exe path row
        path_lbl = QLabel("EXECUTABLE PATH")
        path_lbl.setObjectName("sectionLabel")
        root.addWidget(path_lbl)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select an app above, or use Browse…")
        self.path_edit.setReadOnly(True)
        root.addWidget(self.path_edit)

        # Buttons
        btn_row = QHBoxLayout()
        self.browse_button = QPushButton("Browse .exe…")
        self.browse_button.clicked.connect(self.browse_executable)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveBtn")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_configuration)
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Clear saved config and allow re-selection")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.reset_configuration)
        btn_row.addWidget(self.browse_button)
        btn_row.addStretch()
        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.save_button)
        root.addLayout(btn_row)

        # Load installed apps in background
        self._loader = AppLoaderThread()
        self._loader.apps_loaded.connect(self._on_apps_loaded)
        self._loader.start()

    def check_initial_config(self):
        exe = self.db.get_config("executable_path")
        if exe:
            self._selected_exe = exe
            self._locked = True
            self.path_edit.setText(exe)
            self.search_edit.setEnabled(False)
            self.app_list.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.reset_button.setEnabled(True)
            self.status_label.setText("Executable already configured. Click Reset to change.")

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_apps_loaded(self, apps):
        # type: (List[Tuple[str, str]]) -> None
        self._all_apps = apps
        if not self._locked:
            self._populate_list(apps)
            self.status_label.setText(f"{len(apps)} apps found")

    def _populate_list(self, apps):
        # type: (List[Tuple[str, str]]) -> None
        self.app_list.clear()
        for name, exe in apps:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, exe)
            if exe:
                item.setToolTip(exe)
            else:
                item.setToolTip("Exe not auto-detected — use Browse after selecting")
                item.setForeground(Qt.GlobalColor.gray)
            self.app_list.addItem(item)

    def _filter_list(self, text):
        query = text.lower()
        filtered = [(n, e) for n, e in self._all_apps if query in n.lower()]
        self._populate_list(filtered)
        self.status_label.setText(f"{len(filtered)} apps found")

    def _on_selection_changed(self, current, _prev):
        if current is None:
            return
        exe = current.data(Qt.ItemDataRole.UserRole)
        if exe:
            self._selected_exe = exe
            self.path_edit.setText(exe)
            self.save_button.setEnabled(True)
        else:
            # App found but exe not resolved — clear path and nudge user to Browse
            self._selected_exe = ""
            self.path_edit.clear()
            self.path_edit.setPlaceholderText(
                f"Exe not found for '{current.text()}' — use Browse to locate it"
            )
            self.save_button.setEnabled(False)

    def _on_double_click(self, item):
        exe = item.data(Qt.ItemDataRole.UserRole)
        if exe:
            self._selected_exe = exe
            self.path_edit.setText(exe)
            self.save_configuration()

    def browse_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executable Files (*.exe)"
        )
        if path:
            self._selected_exe = path
            self.path_edit.setText(path)
            self.app_list.clearSelection()
            self.save_button.setEnabled(True)

    def save_configuration(self):
        exe = self._selected_exe or self.path_edit.text()
        if not exe:
            QMessageBox.warning(self, "Warning", "Please select an app or browse to an .exe file.")
            return
        self.db.set_config("executable_path", exe)
        self.configuration_saved.emit(exe)
        self.close()

    def reset_configuration(self):
        self.db.set_config("executable_path", "")
        self._selected_exe = ""
        self._locked = False
        self.path_edit.clear()
        self.path_edit.setPlaceholderText("Select an app above, or use Browse…")
        self.search_edit.setEnabled(True)
        self.app_list.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        # Re-populate if already loaded
        if self._all_apps:
            self._populate_list(self._all_apps)
            self.status_label.setText(f"{len(self._all_apps)} apps found")
        else:
            self.status_label.setText("Loading installed apps…")
        self.search_edit.clear()
        self.search_edit.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ConfigWindow()
    win.show()
    sys.exit(app.exec())


WINDOW_STYLE = """
    QWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QLineEdit {
        background-color: #252525;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 10px;
        color: #e0e0e0;
        font-size: 13px;
    }
    QLineEdit:focus {
        border: 1px solid #4ade80;
    }
    QListWidget {
        background-color: #252525;
        border: 1px solid #333;
        border-radius: 6px;
        outline: none;
    }
    QListWidget::item {
        padding: 8px 12px;
        border-bottom: 1px solid #2a2a2a;
    }
    QListWidget::item:selected {
        background-color: #2d4a35;
        color: #4ade80;
    }
    QListWidget::item:hover:!selected {
        background-color: #2a2a2a;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 7px 18px;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #3a3a3a;
        border: 1px solid #666;
    }
    QPushButton#saveBtn {
        background-color: #1a3a24;
        border: 1px solid #4ade80;
        color: #4ade80;
        font-weight: bold;
    }
    QPushButton#saveBtn:hover {
        background-color: #22502e;
    }
    QPushButton:disabled {
        color: #555;
        border-color: #333;
    }
    QLabel#sectionLabel {
        color: #888;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
    }
    QFrame#separator {
        color: #333;
    }
"""


# ── Registry enumeration ───────────────────────────────────────────────────────

UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _resolve_exe_from_icon(display_icon: str) -> str:
    """Extract the exe path from a DisplayIcon value like 'C:\\app.exe,0'."""
    if not display_icon:
        return ""
    # Strip icon index suffix: "path.exe,0"  or  "path.exe,-1"
    path = display_icon.strip().strip('"')
    if "," in path:
        path = path.rsplit(",", 1)[0].strip()
    path = path.strip('"')
    if path.lower().endswith(".exe") and os.path.isfile(path):
        return path
    return ""


def _find_main_exe(install_location: str) -> str:
    """Try to find a single .exe in the root of the install location."""
    if not install_location or not os.path.isdir(install_location):
        return ""
    try:
        exes = [f for f in os.listdir(install_location) if f.lower().endswith(".exe")]
        if len(exes) == 1:
            return os.path.join(install_location, exes[0])
    except OSError:
        pass
    return ""


def enumerate_installed_apps() -> List[Tuple[str, str]]:
    """
    Return a sorted list of (display_name, exe_path) tuples for installed apps.
    Only includes entries where we can confidently resolve an exe path.
    """
    apps: dict = {}  # name → exe_path (deduplicate by name)

    for hive, key_path in UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(hive, key_path) as root:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(root, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(root, sub_name) as sub:
                            def val(name):
                                try:
                                    return winreg.QueryValueEx(sub, name)[0]
                                except OSError:
                                    return ""

                            display_name     = val("DisplayName").strip()
                            display_icon     = val("DisplayIcon")
                            install_location = val("InstallLocation").strip().strip('"')
                            system_component = val("SystemComponent")

                            # Skip unnamed, system components, and updates
                            if not display_name:
                                continue
                            if system_component == 1:
                                continue
                            if "KB" in sub_name and sub_name.startswith("{") is False:
                                continue

                            exe = _resolve_exe_from_icon(display_icon)
                            if not exe:
                                exe = _find_main_exe(install_location)
                            if not exe:
                                continue

                            if display_name not in apps:
                                apps[display_name] = exe
                    except OSError:
                        continue
        except OSError:
            continue

    return sorted(apps.items(), key=lambda x: x[0].lower())


# ── Background loader thread ───────────────────────────────────────────────────

class AppLoaderThread(QThread):
    apps_loaded = pyqtSignal(list)

    def run(self):
        apps = enumerate_installed_apps()
        self.apps_loaded.emit(apps)


# ── Config window ──────────────────────────────────────────────────────────────

class ConfigWindow(QWidget):
    configuration_saved = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.db = Database()
        self._all_apps: list[tuple[str, str]] = []
        self._selected_exe = ""
        self.init_ui()
        self.check_initial_config()

    def init_ui(self):
        self.setWindowTitle("Tally Counter — Configure")
        self.setMinimumSize(520, 560)
        self.setStyleSheet(WINDOW_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # ── Header ──
        header = QLabel("SELECT APP TO MONITOR")
        header.setObjectName("sectionLabel")
        root.addWidget(header)

        # ── Search box ──
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search installed apps…")
        self.search_edit.textChanged.connect(self._filter_list)
        root.addWidget(self.search_edit)

        # ── App list ──
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(280)
        self.app_list.currentItemChanged.connect(self._on_item_selected)
        self.app_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        loading_item = QListWidgetItem("Loading installed apps…")
        loading_item.setForeground(Qt.GlobalColor.gray)
        loading_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.app_list.addItem(loading_item)
        root.addWidget(self.app_list)

        # ── Selected exe path ──
        path_label = QLabel("EXECUTABLE PATH")
        path_label.setObjectName("sectionLabel")
        root.addWidget(path_label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select an app above or browse manually…")
        self.path_edit.setReadOnly(True)
        root.addWidget(self.path_edit)

        # ── Buttons row ──
        btn_row = QHBoxLayout()
        self.browse_button = QPushButton("Browse .exe…")
        self.browse_button.clicked.connect(self.browse_executable)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveBtn")
        self.save_button.clicked.connect(self.save_configuration)
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Clear saved executable and allow re-selection")
        self.reset_button.clicked.connect(self.reset_configuration)
        btn_row.addWidget(self.browse_button)
        btn_row.addStretch()
        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.save_button)
        root.addLayout(btn_row)

        # Start loading apps in background
        self._loader = AppLoaderThread()
        self._loader.apps_loaded.connect(self._on_apps_loaded)
        self._loader.start()

    def check_initial_config(self):
        exe = self.db.get_config("executable_path")
        if exe:
            self.path_edit.setText(exe)
            self._selected_exe = exe
            self.save_button.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.search_edit.setEnabled(False)
            self.app_list.setEnabled(False)
            self.reset_button.setEnabled(True)
        else:
            self.save_button.setEnabled(False)  # enabled once something is selected
            self.reset_button.setEnabled(False)

    def _on_apps_loaded(self, apps: List[Tuple[str, str]]):
        self._all_apps = apps
        self._populate_list(apps)

    def _populate_list(self, apps: List[Tuple[str, str]]):
        self.app_list.clear()
        if not apps:
            item = QListWidgetItem("No matching apps found")
            item.setForeground(Qt.GlobalColor.gray)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.app_list.addItem(item)
            return
        for name, exe in apps:
            item = QListWidgetItem(name)
            item.setToolTip(exe)
            item.setData(Qt.ItemDataRole.UserRole, exe)
            self.app_list.addItem(item)

    def _filter_list(self, text: str):
        query = text.lower()
        filtered = [(n, e) for n, e in self._all_apps if query in n.lower()]
        self._populate_list(filtered)

    def _on_item_selected(self, current, _previous):
        if current is None:
            return
        exe = current.data(Qt.ItemDataRole.UserRole)
        if exe:
            self._selected_exe = exe
            self.path_edit.setText(exe)
            self.save_button.setEnabled(True)

    def _on_item_double_clicked(self, item):
        """Double-click saves immediately."""
        exe = item.data(Qt.ItemDataRole.UserRole)
        if exe:
            self._selected_exe = exe
            self.path_edit.setText(exe)
            self.save_configuration()

    def browse_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executable Files (*.exe)"
        )
        if path:
            self._selected_exe = path
            self.path_edit.setText(path)
            self.app_list.clearSelection()
            self.save_button.setEnabled(True)

    def save_configuration(self):
        exe = self._selected_exe or self.path_edit.text()
        if not exe:
            QMessageBox.warning(self, "Warning", "Please select an app or browse to an .exe file.")
            return
        self.db.set_config("executable_path", exe)
        self.configuration_saved.emit(exe)
        self.close()

    def reset_configuration(self):
        self.db.set_config("executable_path", "")
        self._selected_exe = ""
        self.path_edit.clear()
        self.save_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.browse_button.setEnabled(True)
        self.search_edit.setEnabled(True)
        self.app_list.setEnabled(True)
        self.search_edit.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ConfigWindow()
    win.show()
    sys.exit(app.exec())

