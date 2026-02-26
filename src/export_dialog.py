import csv
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QCalendarWidget, QFileDialog,
                              QMessageBox, QFrame, QTableWidget,
                              QTableWidgetItem, QHeaderView, QWidget,
                              QSizePolicy, QAbstractItemView)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QBrush

DIALOG_STYLE = """
    QDialog, QWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    QLabel { background: transparent; }
    QCalendarWidget QAbstractItemView {
        background-color: #252525;
        color: #e0e0e0;
        selection-background-color: #2d4a35;
        selection-color: #4ade80;
        border: none;
    }
    QCalendarWidget QWidget#qt_calendar_navigationbar {
        background-color: #1e1e1e;
        padding: 4px;
    }
    QCalendarWidget QToolButton {
        color: #e0e0e0;
        background-color: transparent;
        font-size: 13px;
        font-weight: bold;
        padding: 4px 8px;
    }
    QCalendarWidget QToolButton:hover {
        background-color: #2a2a2a;
        border-radius: 4px;
    }
    QCalendarWidget QSpinBox {
        background-color: #252525;
        color: #e0e0e0;
        border: 1px solid #444;
    }
    QCalendarWidget QAbstractItemView:disabled { color: #555; }
    QTableWidget {
        background-color: #1e1e1e;
        gridline-color: #2a2a2a;
        border: none;
        border-radius: 6px;
        outline: none;
    }
    QTableWidget::item {
        padding: 4px 8px;
        border: none;
    }
    QTableWidget::item:selected {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QHeaderView::section {
        background-color: #252525;
        color: #888;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
        padding: 5px 8px;
        border: none;
        border-bottom: 1px solid #333;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #3a3a3a; border: 1px solid #666; }
    QPushButton:pressed { background-color: #222; }
    QPushButton#quickBtn {
        padding: 4px 12px;
        font-size: 11px;
    }
    QPushButton#exportBtn {
        background-color: #1a3a24;
        border: 1px solid #4ade80;
        color: #4ade80;
        font-weight: bold;
        padding: 7px 22px;
    }
    QPushButton#exportBtn:hover { background-color: #22502e; }
    QPushButton#exportBtn:disabled {
        background-color: #1a1a1a;
        border-color: #333;
        color: #555;
    }
    QFrame#sep { color: #333; }
    QLabel#section { color: #888; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
    QLabel#info { color: #aaa; font-size: 12px; }
    QScrollBar:vertical {
        background: #1a1a1a;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #444;
        border-radius: 4px;
        min-height: 20px;
    }
"""

RANGE_FMT = QTextCharFormat()
RANGE_FMT.setBackground(QColor("#1a3a24"))
RANGE_FMT.setForeground(QColor("#4ade80"))

ENDPOINT_FMT = QTextCharFormat()
ENDPOINT_FMT.setBackground(QColor("#4ade80"))
ENDPOINT_FMT.setForeground(QColor("#111"))
ENDPOINT_FMT.setFontWeight(QFont.Weight.Bold)

CLEAR_FMT = QTextCharFormat()


def _sep(parent=None):
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("sep")
    return line


class ExportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.start_date = None   # QDate
        self.end_date = None     # QDate
        self._picking = "start"  # "start" | "end"
        self._all_rows = []      # cached db rows for current selection

        self.setWindowTitle("Export Data")
        self.setMinimumWidth(520)
        self.setMinimumHeight(680)
        self.setStyleSheet(DIALOG_STYLE)
        self._init_ui()

    # ── UI setup ───────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        # --- Quick presets ---
        pl = QLabel("QUICK SELECT")
        pl.setObjectName("section")
        root.addWidget(pl)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for label, fn in [
            ("This Month",   self._preset_this_month),
            ("Last Month",   self._preset_last_month),
            ("Last 7 Days",  self._preset_last_7),
            ("Last 30 Days", self._preset_last_30),
            ("All Time",     self._preset_all_time),
        ]:
            b = QPushButton(label)
            b.setObjectName("quickBtn")
            b.clicked.connect(fn)
            preset_row.addWidget(b)
        preset_row.addStretch()
        root.addLayout(preset_row)

        root.addWidget(_sep())

        # --- Calendar + instruction ---
        cal_lbl = QLabel("DATE RANGE")
        cal_lbl.setObjectName("section")
        root.addWidget(cal_lbl)

        self.instruction_lbl = QLabel("Click a start date, then an end date.")
        self.instruction_lbl.setObjectName("info")
        root.addWidget(self.instruction_lbl)

        # Single calendar, full width
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.calendar.clicked.connect(self._on_date_clicked)
        root.addWidget(self.calendar)

        root.addWidget(_sep())

        # --- Data table ---
        tbl_header_row = QHBoxLayout()
        tbl_lbl = QLabel("RECORDED DATA")
        tbl_lbl.setObjectName("section")
        self.range_summary_lbl = QLabel("")
        self.range_summary_lbl.setObjectName("info")
        self.range_summary_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tbl_header_row.addWidget(tbl_lbl)
        tbl_header_row.addStretch()
        tbl_header_row.addWidget(self.range_summary_lbl)
        root.addLayout(tbl_header_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Date", "Day", "Max Instances"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setFixedHeight(180)
        root.addWidget(self.table)

        root.addWidget(_sep())

        # --- Bottom row ---
        bottom = QHBoxLayout()
        self.status_lbl = QLabel("No range selected.")
        self.status_lbl.setObjectName("info")
        bottom.addWidget(self.status_lbl, 1)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._do_export)
        bottom.addWidget(clear_btn)
        bottom.addWidget(self.export_btn)
        root.addLayout(bottom)

    # ── Calendar interaction ───────────────────────────────────────────────────

    def _on_date_clicked(self, q_date):
        if self._picking == "start" or self.start_date is None:
            self.start_date = q_date
            self.end_date = None
            self._picking = "end"
        else:
            if q_date < self.start_date:
                self.start_date, self.end_date = q_date, self.start_date
            else:
                self.end_date = q_date
            self._picking = "start"
        self._refresh()

    def _apply_range(self, start, end):
        self.start_date = start
        self.end_date = end
        self._picking = "start"
        self.calendar.setCurrentPage(start.year(), start.month())
        self._refresh()

    def _clear(self):
        self.start_date = None
        self.end_date = None
        self._picking = "start"
        self._refresh()

    # ── Highlight calendar ─────────────────────────────────────────────────────

    def _highlight_calendar(self):
        # Clear a wide window around today
        today = QDate.currentDate()
        for d in range(-400, 400):
            self.calendar.setDateTextFormat(today.addDays(d), CLEAR_FMT)

        if self.start_date and self.end_date:
            d = self.start_date
            while d <= self.end_date:
                if d == self.start_date or d == self.end_date:
                    self.calendar.setDateTextFormat(d, ENDPOINT_FMT)
                else:
                    self.calendar.setDateTextFormat(d, RANGE_FMT)
                d = d.addDays(1)
        elif self.start_date:
            self.calendar.setDateTextFormat(self.start_date, ENDPOINT_FMT)

    # ── Populate data table ────────────────────────────────────────────────────

    def _populate_table(self):
        self.table.setRowCount(0)
        if not self.start_date or not self.end_date:
            return

        start_str = self.start_date.toString("yyyy-MM-dd")
        end_str   = self.end_date.toString("yyyy-MM-dd")
        rows = self.db.get_counts_for_range(start_str, end_str)
        self._all_rows = rows

        # Build a lookup for fast access
        data = {r[0]: r[1] for r in rows}

        # Walk every day in the range
        d = self.start_date
        row_idx = 0
        while d <= self.end_date:
            date_str  = d.toString("yyyy-MM-dd")
            day_name  = d.toString("dddd")
            max_inst  = data.get(date_str)

            self.table.insertRow(row_idx)

            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            day_item = QTableWidgetItem(day_name)
            day_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            if max_inst is not None:
                val_item = QTableWidgetItem(str(max_inst))
                val_item.setForeground(QBrush(QColor("#4ade80")))
            else:
                val_item = QTableWidgetItem("—")
                val_item.setForeground(QBrush(QColor("#555")))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Dim rows with no data
            if max_inst is None:
                date_item.setForeground(QBrush(QColor("#555")))
                day_item.setForeground(QBrush(QColor("#555")))

            self.table.setItem(row_idx, 0, date_item)
            self.table.setItem(row_idx, 1, day_item)
            self.table.setItem(row_idx, 2, val_item)
            row_idx += 1
            d = d.addDays(1)

        self.table.scrollToTop()

    # ── Refresh all state ──────────────────────────────────────────────────────

    def _refresh(self):
        self._highlight_calendar()
        self._populate_table()

        if self.start_date and self.end_date:
            days   = self.start_date.daysTo(self.end_date) + 1
            points = len(self._all_rows)
            self.instruction_lbl.setText(
                f"{self.start_date.toString('dd MMM yyyy')}  →  "
                f"{self.end_date.toString('dd MMM yyyy')}"
            )
            self.range_summary_lbl.setText(f"{days} days  ·  {points} recorded")
            self.status_lbl.setText(
                "No data in range." if points == 0 else f"{points} rows ready to export."
            )
            self.export_btn.setEnabled(points > 0)
        elif self.start_date:
            self.instruction_lbl.setText(
                f"Start: {self.start_date.toString('dd MMM yyyy')}  —  now pick an end date."
            )
            self.range_summary_lbl.setText("")
            self.status_lbl.setText("")
            self.export_btn.setEnabled(False)
        else:
            self.instruction_lbl.setText("Click a start date, then an end date.")
            self.range_summary_lbl.setText("")
            self.status_lbl.setText("No range selected.")
            self.export_btn.setEnabled(False)

    # ── Presets ────────────────────────────────────────────────────────────────

    def _preset_this_month(self):
        t = QDate.currentDate()
        self._apply_range(QDate(t.year(), t.month(), 1),
                          QDate(t.year(), t.month(), t.daysInMonth()))

    def _preset_last_month(self):
        first = QDate.currentDate().addMonths(-1)
        first = QDate(first.year(), first.month(), 1)
        self._apply_range(first, QDate(first.year(), first.month(), first.daysInMonth()))

    def _preset_last_7(self):
        end = QDate.currentDate()
        self._apply_range(end.addDays(-6), end)

    def _preset_last_30(self):
        end = QDate.currentDate()
        self._apply_range(end.addDays(-29), end)

    def _preset_all_time(self):
        rows = self.db.get_counts_for_range("0000-01-01", "9999-12-31")
        if not rows:
            QMessageBox.information(self, "No Data", "No data recorded yet.")
            return
        dates = [r[0] for r in rows]
        self._apply_range(QDate.fromString(min(dates), "yyyy-MM-dd"),
                          QDate.fromString(max(dates), "yyyy-MM-dd"))

    # ── Export ─────────────────────────────────────────────────────────────────

    def _do_export(self):
        if not self._all_rows:
            return

        exe_path = self.db.get_config("executable_path") or ""
        app_name = os.path.splitext(os.path.basename(exe_path))[0] if exe_path else "TallyCounter"
        start_str = self.start_date.toString("yyyy-MM-dd")
        end_str   = self.end_date.toString("yyyy-MM-dd")
        suggested = f"{app_name}_{start_str}_to_{end_str}.csv"

        save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", suggested, "CSV Files (*.csv)")
        if not save_path:
            return

        exe_name = os.path.basename(exe_path) if exe_path else "Unknown"
        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Application", "Max Instances"])
            for date_str, max_inst in self._all_rows:
                # Prefix with ="..." so Excel treats as text, not a date
                # (prevents auto-parsing and the #### column-width issue)
                writer.writerow([f'="{date_str}"', exe_name, max_inst])

        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(self._all_rows)} rows to:\n{save_path}"
        )
        self.accept()
