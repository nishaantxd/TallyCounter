import psutil
import os
import sys
import threading
from datetime import datetime
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from database import Database



class MonitorWorker(QObject):
    instance_count_updated = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, executable_path):
        super().__init__()
        self.executable_path = executable_path
        self.executable_name = os.path.basename(executable_path)
        self._is_running = True
        self._stop_event = threading.Event()
        self.db = Database()

    def run(self):
        if not os.path.exists(self.executable_path):
            self.error.emit(f"Error: Executable not found at '{self.executable_path}'")
            return

        while self._is_running:
            try:
                count = 0
                if sys.platform == 'win32':
                    # Count top-level instances only (processes whose parent is NOT the same executable).
                    # This correctly handles multi-process apps like Chrome (renderer/GPU processes have
                    # chrome.exe as their parent and are excluded) while counting all independent instances
                    # of console/background apps like python.exe or tally.exe.
                    main_pids = set()
                    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe']):
                        try:
                            if proc.info['name'].lower() == self.executable_name.lower() and proc.info['exe'] and os.path.samefile(proc.info['exe'], self.executable_path):
                                parent = psutil.Process(proc.info['ppid']) if proc.info['ppid'] else None
                                parent_is_same = False
                                if parent:
                                    try:
                                        parent_is_same = (
                                            parent.name().lower() == self.executable_name.lower()
                                            and parent.exe()
                                            and os.path.samefile(parent.exe(), self.executable_path)
                                        )
                                    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                                        pass
                                if not parent_is_same:
                                    main_pids.add(proc.info['pid'])
                        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                            continue
                    count = len(main_pids)
                else:
                    # Default logic for non-Windows platforms
                    main_pids = set()
                    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe']):
                        try:
                            if proc.info['name'] == self.executable_name and proc.info['exe'] and os.path.samefile(proc.info['exe'], self.executable_path):
                                parent = psutil.Process(proc.info['ppid']) if proc.info['ppid'] else None
                                if not parent or parent.name() != self.executable_name or (parent.exe() if parent.exe() else None) != self.executable_path:
                                    main_pids.add(proc.info['pid'])
                        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                            continue
                    count = len(main_pids)

                today_str = datetime.now().strftime('%Y-%m-%d')
                self.db.update_daily_max(today_str, count)
                self.instance_count_updated.emit(count)

            except Exception as e:
                self.error.emit(str(e))
            # Wait up to 60 seconds, but wake immediately if stop() is called
            self._stop_event.wait(timeout=60)
            self._stop_event.clear()

    def stop(self):
        self._is_running = False
        self._stop_event.set()  # Wake up the sleeping thread immediately

class ProcessMonitor:
    def __init__(self, executable_path):
        self.thread = QThread()
        self.worker = MonitorWorker(executable_path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.instance_count_updated.connect(self.on_instance_count_updated)
        self.worker.error.connect(self.on_error)

    def start(self):
        self.thread.start()

    def stop(self):
        self.worker.stop()
        self.thread.quit()
        self.thread.wait(3000)  # Wait max 3 seconds then force stop

    def on_instance_count_updated(self, count):
        print(f"Running instances: {count}")

    def on_error(self, err_msg):
        print(err_msg)

