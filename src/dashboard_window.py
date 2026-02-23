import os
import psutil
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame)
from PyQt6.QtCore import QTimer, QDate, Qt
from PyQt6.QtGui import QFont, QIcon
from heatmap_widget import CalendarHeatmap
from database import Database

APP_STYLE = """
    QMainWindow, QWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 18px;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #3a3a3a;
        border: 1px solid #666;
    }
    QPushButton:pressed {
        background-color: #222;
    }
"""

STAT_CARD_STYLE = """
    QFrame {
        background-color: #252525;
        border-radius: 10px;
        border: 1px solid #333;
    }
"""

STAT_VALUE_STYLE = "color: #4ade80; font-size: 22px; font-weight: bold;"
STAT_LABEL_STYLE = "color: #888; font-size: 11px; font-weight: 500; letter-spacing: 1px;"
MONTH_LABEL_STYLE = "color: #e0e0e0; font-size: 16px; font-weight: bold;"


def make_stat_card(title, initial_value):
    frame = QFrame()
    frame.setStyleSheet(STAT_CARD_STYLE)
    frame.setFixedHeight(80)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 10, 16, 10)
    layout.setSpacing(2)
    title_lbl = QLabel(title.upper())
    title_lbl.setStyleSheet(STAT_LABEL_STYLE)
    value_lbl = QLabel(initial_value)
    value_lbl.setStyleSheet(STAT_VALUE_STYLE)
    layout.addWidget(title_lbl)
    layout.addWidget(value_lbl)
    return frame, value_lbl


class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        # Prime CPU percent so first read is non-zero
        psutil.cpu_percent(interval=None)
        self.init_ui()
        self.load_heatmap_data()

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_current_time)
        self.time_timer.start(1000)

        # Update CPU/RAM every 2 seconds (efficient, non-blocking)
        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self.update_system_stats)
        self.sys_timer.start(2000)

    def init_ui(self):
        self.setWindowTitle('Tally Counter')
        self.setMinimumSize(600, 520)
        self.setStyleSheet(APP_STYLE)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # --- Stat Cards Row ---
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        time_card, self.current_time_label = make_stat_card("System Time", datetime.now().strftime('%H:%M:%S'))
        count_card, self.current_count_label = make_stat_card("Running Now", "N/A")
        max_card, self.today_max_label = make_stat_card("Today's Max", "N/A")
        cpu_card, self.cpu_label = make_stat_card("CPU Usage", "...")
        ram_card, self.ram_label = make_stat_card("RAM Usage", "...")

        cards_layout.addWidget(time_card)
        cards_layout.addWidget(count_card)
        cards_layout.addWidget(max_card)
        cards_layout.addWidget(cpu_card)
        cards_layout.addWidget(ram_card)
        root.addLayout(cards_layout)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        root.addWidget(sep)

        # --- Month Navigation ---
        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("‹ Prev")
        next_btn = QPushButton("Next ›")
        prev_btn.setFixedWidth(80)
        next_btn.setFixedWidth(80)
        prev_btn.clicked.connect(self.prev_month_action)
        next_btn.clicked.connect(self.next_month_action)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet(MONTH_LABEL_STYLE)
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.month_label)
        nav_layout.addStretch()
        nav_layout.addWidget(next_btn)
        root.addLayout(nav_layout)

        # --- Heatmap (centered) ---
        self.heatmap = CalendarHeatmap()
        root.addWidget(self.heatmap, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addStretch()

        self.update_current_time()
        self.update_month_label()

    def update_current_time(self):
        self.current_time_label.setText(datetime.now().strftime('%H:%M:%S'))

    def update_system_stats(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        self.cpu_label.setText(f"{cpu:.1f}%")
        used_gb = ram.used / (1024 ** 3)
        total_gb = ram.total / (1024 ** 3)
        self.ram_label.setText(f"{used_gb:.1f} / {total_gb:.1f} GB")

    def update_live_counts(self, current_count):
        self.current_count_label.setText(str(current_count))
        today_str = datetime.now().strftime('%Y-%m-%d')
        max_count_today = self.db.get_counts_for_month(datetime.now().year, datetime.now().month)
        today_data = [item for item in max_count_today if item[0] == today_str]
        self.today_max_label.setText(str(today_data[0][1]) if today_data else "0")
        self.heatmap.set_data(self.heatmap.data, db=self.db, live_count=current_count)

    def load_heatmap_data(self):
        year = self.heatmap.current_date.year()
        month = self.heatmap.current_date.month()
        counts = self.db.get_counts_for_month(year, month)
        data_for_heatmap = {}
        for date_str, count in counts:
            q_date = QDate.fromString(date_str, 'yyyy-MM-dd')
            data_for_heatmap[q_date] = count
        self.heatmap.set_data(data_for_heatmap, db=self.db, live_count=self.get_live_count())
        self.update_month_label()

    def get_live_count(self):
        try:
            return int(self.current_count_label.text())
        except Exception:
            return None

    def prev_month_action(self):
        self.heatmap.prev_month()
        self.load_heatmap_data()

    def next_month_action(self):
        self.heatmap.next_month()
        self.load_heatmap_data()
        
    def update_month_label(self):
        self.month_label.setText(self.heatmap.current_date.toString("MMMM yyyy"))

    def closeEvent(self, event):
        # Hide the window instead of closing it (tray app stays alive)
        event.ignore()
        self.hide()

