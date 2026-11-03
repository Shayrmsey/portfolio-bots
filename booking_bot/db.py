import sqlite3
from contextlib import contextmanager
from datetime import date


class Database:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    service TEXT NOT NULL,
                    day TEXT NOT NULL,
                    time TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (day, time)
                )
                """
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def busy_slots(self, day: str) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT time FROM bookings WHERE day = ?", (day,))
            return {row["time"] for row in rows}

    def add(self, user_id: int, service: str, day: str, time: str, name: str, phone: str) -> int | None:
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO bookings (user_id, service, day, time, name, phone) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, service, day, time, name, phone),
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def user_upcoming(self, user_id: int) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM bookings WHERE user_id = ? AND day >= ? ORDER BY day, time",
                (user_id, date.today().isoformat()),
            ).fetchall()

    def all_upcoming(self) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM bookings WHERE day >= ? ORDER BY day, time",
                (date.today().isoformat(),),
            ).fetchall()

    def cancel(self, booking_id: int, user_id: int) -> sqlite3.Row | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM bookings WHERE id = ? AND user_id = ?", (booking_id, user_id)
            ).fetchone()
            if row:
                conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            return row
