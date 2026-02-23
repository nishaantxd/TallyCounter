import sys
import os
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer
from database import Database
from config_window import ConfigWindow
from dashboard_window import DashboardWindow
from monitor import ProcessMonitor
import startup

class TallyCounterApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.db = Database()
        self.config_window = None
        self.dashboard_window = DashboardWindow()
        self.monitor = None

        # Keep a persistent reference to the tray icon
        self._tray_icon_ref = self.create_icon()
        self.tray_icon = QSystemTrayIcon(self._tray_icon_ref)
        self.tray_icon.setToolTip("Tally Counter")
        self.tray_menu = QMenu()

        self.action_open = QAction("Open Dashboard")
        self.action_config = QAction("Configure")
        self.action_startup = QAction("Start with Windows")
        self.action_startup.setCheckable(True)
        self.action_startup.setChecked(startup.is_startup_enabled())
        self.action_exit = QAction("Exit")

        self.action_open.triggered.connect(self.show_dashboard)
        self.action_config.triggered.connect(self.show_config_window)
        self.action_startup.triggered.connect(self.toggle_startup)
        self.action_exit.triggered.connect(self.exit_app)

        self.tray_menu.addAction(self.action_open)
        self.tray_menu.addAction(self.action_config)
        self.tray_menu.addAction(self.action_startup)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.action_exit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

        # Ensure the tray icon stays visible and config window pops up if needed
        QTimer.singleShot(0, self.check_initial_configuration)

    def create_icon(self):
        # Place 'icon.ico' or 'icon.png' in the src/ directory to use a custom tray icon.
        icon_path_ico = os.path.join(os.path.dirname(__file__), "icon.ico")
        icon_path_png = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path_ico):
            return QIcon(icon_path_ico)
        elif os.path.exists(icon_path_png):
            return QIcon(icon_path_png)
        else:
            return QIcon.fromTheme("system-run")

    def check_initial_configuration(self):
        executable_path = self.db.get_config('executable_path')
        if not executable_path:
            self.show_config_window()
        else:
            self.start_monitoring(executable_path)

    def show_config_window(self):
        if not self.config_window:
            self.config_window = ConfigWindow()
            self.config_window.configuration_saved.connect(self.on_configuration_saved)
        self.config_window.show()

    def on_configuration_saved(self, executable_path):
        self.start_monitoring(executable_path)
        self.show_dashboard()

    def start_monitoring(self, executable_path):
        if self.monitor:
            self.monitor.stop()
        self.monitor = ProcessMonitor(executable_path)
        self.monitor.worker.instance_count_updated.connect(self.dashboard_window.update_live_counts)
        self.monitor.worker.error.connect(self.handle_monitor_error)
        self.dashboard_window.refresh_requested.connect(self.monitor.worker.force_poll)
        self.monitor.start()
        self.dashboard_window.load_heatmap_data()

    def handle_monitor_error(self, error_message):
        print(f"Monitoring Error: {error_message}")
        self.dashboard_window.current_count_label.setText("Err")

    def show_dashboard(self):
        self.dashboard_window.load_heatmap_data()
        self.dashboard_window.show()
        self.dashboard_window.raise_()
        self.dashboard_window.activateWindow()

    def toggle_startup(self, checked: bool):
        if checked:
            startup.enable_startup()
        else:
            startup.disable_startup()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_dashboard()

    def run(self):
        sys.exit(self.app.exec())

    def exit_app(self):
        if self.monitor:
            self.monitor.stop()
        self.tray_icon.hide()
        self.app.quit()

def main():
    app = TallyCounterApp()
    app.run()

if __name__ == "__main__":
    main()
