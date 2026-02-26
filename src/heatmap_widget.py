from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QMessageBox, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont

CELL_SIZE = 48
CELL_HEIGHT = 70   # 48 date box + 4 gap + 18 count pill
CELL_RADIUS = 8
PILL_RADIUS = 5

DAY_LABEL_STYLE = """
    QLabel {
        color: #888;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 0;
    }
"""


class ClickableCell(QWidget):
    """Two-piece cell: thick square box for the date, thin pill for the count."""
    def __init__(self, date, parent=None):
        super().__init__(parent)
        self.date = date
        self.click_callback = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # ── Thick box: date number ──────────────────────────────────────────
        self.date_box = QFrame()
        self.date_box.setObjectName("dateBox")
        self.date_box.setFixedSize(CELL_SIZE, CELL_SIZE)
        db_lay = QVBoxLayout(self.date_box)
        db_lay.setContentsMargins(0, 0, 0, 0)
        self.day_lbl = QLabel(str(date.day()))
        self.day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        day_font = QFont()
        day_font.setPointSize(11)
        day_font.setBold(True)
        self.day_lbl.setFont(day_font)
        self.day_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        db_lay.addWidget(self.day_lbl)

        # ── Thin pill: count ────────────────────────────────────────────────
        self.count_box = QFrame()
        self.count_box.setObjectName("countBox")
        self.count_box.setFixedSize(CELL_SIZE, 18)
        cb_lay = QVBoxLayout(self.count_box)
        cb_lay.setContentsMargins(0, 0, 0, 0)
        self.count_lbl = QLabel("")
        self.count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_font = QFont()
        count_font.setPointSize(7)
        count_font.setBold(True)
        self.count_lbl.setFont(count_font)
        self.count_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        cb_lay.addWidget(self.count_lbl)

        lay.addWidget(self.date_box)
        lay.addWidget(self.count_box)

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
        self.container.setMaximumWidth(CELL_SIZE * 7 + 6 * 10)  # 7 cells + 6 gaps of 10px
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(10)
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
        cell = ClickableCell(date)
        cell.setFixedSize(CELL_SIZE, CELL_HEIGHT)

        if color is None:
            # No data — muted cells
            cell.setStyleSheet(f"""
                QWidget {{ background: transparent; }}
                QFrame#dateBox {{
                    background-color: #2a2a2a;
                    border: 1px solid #111;
                    border-radius: {CELL_RADIUS}px;
                }}
                QFrame#dateBox:hover {{
                    background-color: #383838;
                    border: 1px solid #3a3a3a;
                }}
                QFrame#countBox {{
                    background-color: #1e1e1e;
                    border: 1px solid #111;
                    border-radius: {PILL_RADIUS}px;
                }}
            """)
            cell.day_lbl.setStyleSheet("color: #666; background: transparent;")
            cell.count_lbl.setStyleSheet("color: transparent; background: transparent;")
        else:
            # Has data — green date box + darker green pill
            pill = color.darker(125)
            cell.setStyleSheet(f"""
                QWidget {{ background: transparent; }}
                QFrame#dateBox {{
                    background-color: {color.name()};
                    border: 1px solid {color.darker(145).name()};
                    border-radius: {CELL_RADIUS}px;
                }}
                QFrame#dateBox:hover {{
                    background-color: {color.lighter(115).name()};
                    border: 1px solid {color.name()};
                }}
                QFrame#countBox {{
                    background-color: {pill.name()};
                    border: 1px solid {color.darker(160).name()};
                    border-radius: {PILL_RADIUS}px;
                }}
            """)
            cell.day_lbl.setStyleSheet("color: #071a0d; background: transparent;")
            cell.count_lbl.setStyleSheet("color: #071a0d; background: transparent;")
            cell.count_lbl.setText(str(count))

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

