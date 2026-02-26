import sqlite3
import os
import sys

def get_data_dir():
    # When frozen by PyInstaller, store db next to the .exe
    # When running normally, store next to the script
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class Database:
    def __init__(self, db_name='tally_counter.db'):
        self.db_path = os.path.join(get_data_dir(), db_name)
        # Allow connections across threads, but each instance should be used in one thread only
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_counts (
                    date TEXT PRIMARY KEY,
                    max_instances INTEGER NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    def set_config(self, key, value):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO config (key, value)
                VALUES (?, ?)
            """, (key, value))

    def get_config(self, key):
        with self.conn:
            cursor = self.conn.execute("SELECT value FROM config WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else None

    def update_daily_max(self, date, count):
        with self.conn:
            cursor = self.conn.execute("SELECT max_instances FROM daily_counts WHERE date = ?", (date,))
            result = cursor.fetchone()
            if result:
                if count > result[0]:
                    self.conn.execute("UPDATE daily_counts SET max_instances = ? WHERE date = ?", (count, date))
            else:
                self.conn.execute("INSERT INTO daily_counts (date, max_instances) VALUES (?, ?)", (date, count))

    def get_counts_for_month(self, year, month):
        date_prefix = f"{year}-{month:02d}"
        with self.conn:
            cursor = self.conn.execute("SELECT date, max_instances FROM daily_counts WHERE date LIKE ?", (date_prefix + '%',))
            return cursor.fetchall()

    def get_counts_for_range(self, start_date, end_date):
        """Return rows where date is between start_date and end_date (inclusive, 'YYYY-MM-DD' strings)."""
        with self.conn:
            cursor = self.conn.execute(
                "SELECT date, max_instances FROM daily_counts WHERE date >= ? AND date <= ? ORDER BY date",
                (start_date, end_date)
            )
            return cursor.fetchall()

