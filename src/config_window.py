import os
import sys
import winreg
from typing import List, Tuple
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


# â”€â”€ Registry enumeration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    apps: dict = {}  # name â†’ exe_path (deduplicate by name)

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


# â”€â”€ Background loader thread â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AppLoaderThread(QThread):
    apps_loaded = pyqtSignal(list)

    def run(self):
        apps = enumerate_installed_apps()
        self.apps_loaded.emit(apps)


# â”€â”€ Config window â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        self.setWindowTitle("Tally Counter â€” Configure")
        self.setMinimumSize(520, 560)
        self.setStyleSheet(WINDOW_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # â”€â”€ Header â”€â”€
        header = QLabel("SELECT APP TO MONITOR")
        header.setObjectName("sectionLabel")
        root.addWidget(header)

        # â”€â”€ Search box â”€â”€
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search installed appsâ€¦")
        self.search_edit.textChanged.connect(self._filter_list)
        root.addWidget(self.search_edit)

        # â”€â”€ App list â”€â”€
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(280)
        self.app_list.currentItemChanged.connect(self._on_item_selected)
        self.app_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        loading_item = QListWidgetItem("Loading installed appsâ€¦")
        loading_item.setForeground(Qt.GlobalColor.gray)
        loading_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.app_list.addItem(loading_item)
        root.addWidget(self.app_list)

        # â”€â”€ Selected exe path â”€â”€
        path_label = QLabel("EXECUTABLE PATH")
        path_label.setObjectName("sectionLabel")
        root.addWidget(path_label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select an app above or browse manuallyâ€¦")
        self.path_edit.setReadOnly(True)
        root.addWidget(self.path_edit)

        # â”€â”€ Buttons row â”€â”€
        btn_row = QHBoxLayout()
        self.browse_button = QPushButton("Browse .exeâ€¦")
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
