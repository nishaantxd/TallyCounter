from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QMessageBox, QVBoxLayout
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont

CELL_SIZE = 48
CELL_RADIUS = 8

DAY_LABEL_STYLE = """
    QLabel {
        color: #888;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 0;
    }
"""


class ClickableLabel(QLabel):
    def __init__(self, date, parent=None):
        super().__init__(str(date.day()), parent)
        self.date = date
        self.click_callback = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if self.click_callback:
            self.click_callback(self.date)


class CalendarHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_date = QDate.currentDate()
        self.data = {}
        self.db = None
        self.live_count = None
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.container = QWidget()
        self.container.setMaximumWidth(CELL_SIZE * 7 + 60)
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(6)
        self.grid.setContentsMargins(0, 0, 0, 0)

        outer.addWidget(self.container)
        self.update_calendar()

    def set_data(self, data, db=None, live_count=None):
        self.data = data
        self.db = db
        self.live_count = live_count
        self.update_calendar()

    def update_calendar(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        days_in_month = self.current_date.daysInMonth()
        first_day = QDate(self.current_date.year(), self.current_date.month(), 1)
        first_day_of_week = first_day.dayOfWeek() - 1  # Monday=0

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(28)
            label.setStyleSheet(DAY_LABEL_STYLE)
            self.grid.addWidget(label, 0, i)

        max_val = max(self.data.values()) if self.data else 1

        row = 1
        col = first_day_of_week
        for day in range(1, days_in_month + 1):
            date = QDate(self.current_date.year(), self.current_date.month(), day)
            count = self.data.get(date, 0)
            color = self.get_color_for_count(count, max_val)
            cell = self.create_cell(date, count, color)
            self.grid.addWidget(cell, row, col)
            col += 1
            if col > 6:
                col = 0
                row += 1

        for i in range(7):
            self.grid.setColumnStretch(i, 1)

    def get_color_for_count(self, count, max_val):
        if count == 0:
            return None
        ratio = count / max_val
        # Green gradient: low=muted, high=vibrant
        r = int(30 + 60 * (1 - ratio))
        g = int(180 + 55 * ratio)
        b = int(50 + 30 * (1 - ratio))
        return QColor(r, g, b)

    def create_cell(self, date, count, color):
        cell = ClickableLabel(date)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.setFixedSize(CELL_SIZE, CELL_SIZE)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        cell.setFont(font)
        if color is None:
            cell.setStyleSheet(f"""
                QLabel {{
                    background-color: #2a2a2a;
                    color: #666;
                    border-radius: {CELL_RADIUS}px;
                }}
                QLabel:hover {{
                    background-color: #3a3a3a;
                    color: #aaa;
                }}
            """)
        else:
            cell.setStyleSheet(f"""
                QLabel {{
                    background-color: {color.name()};
                    color: #111;
                    border-radius: {CELL_RADIUS}px;
                }}
                QLabel:hover {{
                    background-color: {color.lighter(120).name()};
                    color: #000;
                }}
            """)
        cell.setToolTip(f"Date: {date.toString('yyyy-MM-dd')}\nMax Count: {count}")
        cell.click_callback = self.show_day_info
        return cell

    def show_day_info(self, date):
        date_str = date.toString('yyyy-MM-dd')
        max_count = None
        if self.db:
            try:
                result = self.db.conn.execute(
                    "SELECT max_instances FROM daily_counts WHERE date = ?", (date_str,)
                ).fetchone()
                if result:
                    max_count = result[0]
            except Exception:
                pass
        today_str = QDate.currentDate().toString('yyyy-MM-dd')
        current_count = self.live_count if (date_str == today_str and self.live_count is not None) else 'N/A'
        max_display = max_count if max_count is not None else 'None'
        QMessageBox.information(
            self, "Day Info",
            f"Date:              {date_str}\nMax Instances:  {max_display}\nCurrent:           {current_count}"
        )

    def next_month(self):
        self.current_date = self.current_date.addMonths(1)
        self.update_calendar()

    def prev_month(self):
        self.current_date = self.current_date.addMonths(-1)
        self.update_calendar()

