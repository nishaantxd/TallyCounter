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

        last_count = -1
        while self._is_running:
            try:
                count = self._count_instances()
                if count != last_count:
                    last_count = count
                    today_str = datetime.now().strftime('%Y-%m-%d')
                    self.db.update_daily_max(today_str, count)
                    self.instance_count_updated.emit(count)
            except Exception as e:
                self.error.emit(str(e))
            # Check every 5 seconds so the UI reacts quickly when instances start/stop.
            # Wakes immediately if stop() is called.
            self._stop_event.wait(timeout=5)
            self._stop_event.clear()

    def _same_exe(self, path_a: str, path_b: str) -> bool:
        """Return True if two paths refer to the same file, with a name-only fallback."""
        try:
            return os.path.samefile(path_a, path_b)
        except (FileNotFoundError, OSError):
            # Fallback: compare just the filenames (handles Store/UWP apps whose
            # actual exe path differs from what was saved in config, e.g. Notepad on Win11)
            return os.path.basename(path_a).lower() == os.path.basename(path_b).lower()

    def _count_instances(self) -> int:
        """Count the number of top-level running instances of the monitored executable."""
        main_pids = set()
        name_lower = self.executable_name.lower()

        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe']):
            try:
                proc_name = proc.info['name']
                proc_exe  = proc.info['exe']

                # Match by name first (fast check)
                if sys.platform == 'win32':
                    if proc_name.lower() != name_lower:
                        continue
                else:
                    if proc_name != self.executable_name:
                        continue

                # Match by path if available; fall back to name-only match for
                # Store/UWP apps (e.g. Notepad on Windows 11) where the exe path
                # differs from the path stored in config.
                if proc_exe and not self._same_exe(proc_exe, self.executable_path):
                    continue

                # Exclude child processes whose parent is the same executable
                # (handles multi-process apps like Chrome, Electron, etc.)
                parent_is_same = False
                ppid = proc.info['ppid']
                if ppid:
                    try:
                        parent = psutil.Process(ppid)
                        parent_name = parent.name()
                        if sys.platform == 'win32':
                            parent_is_same = parent_name.lower() == name_lower
                        else:
                            parent_is_same = parent_name == self.executable_name
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                if not parent_is_same:
                    main_pids.add(proc.info['pid'])

            except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                continue

        return len(main_pids)

    def force_poll(self):
        """Trigger an immediate count without waiting for the next 5-second tick."""
        self._stop_event.set()

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
        pass

    def on_error(self, err_msg):
        pass

