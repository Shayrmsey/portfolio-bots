import asyncio
import csv
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import astuple, dataclass, fields

from config import Config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lead:
    created_at: str
    name: str
    phone: str
    service: str
    comment: str
    username: str


HEADER = [f.name for f in fields(Lead)]


class LeadStorage:
    def __init__(self, config: Config):
        self.csv_path = config.csv_path
        self.sheet = None
        if config.sheet_id and os.path.exists(config.credentials_file):
            import gspread

            client = gspread.service_account(filename=config.credentials_file)
            self.sheet = client.open_by_key(config.sheet_id).sheet1
            if not self.sheet.row_values(1):
                self.sheet.append_row(HEADER)
            log.info("Заявки зберігаються в Google Таблицю")
        else:
            log.info("Google Таблицю не налаштовано, заявки зберігаються в %s", self.csv_path)

    def _append_csv(self, lead: Lead) -> None:
        is_new = not os.path.exists(self.csv_path)
        with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(HEADER)
            writer.writerow(astuple(lead))

    def _append(self, lead: Lead) -> None:
        if self.sheet is None:
            self._append_csv(lead)
            return
        try:
            self.sheet.append_row(list(astuple(lead)), value_input_option="USER_ENTERED")
        except Exception:
            log.exception("Не вдалося записати в Google Таблицю, зберігаю в CSV")
            self._append_csv(lead)

    async def save(self, lead: Lead) -> None:
        await asyncio.to_thread(self._append, lead)


class Users:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1)")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def add(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (id) VALUES (?) ON CONFLICT (id) DO UPDATE SET active = 1", (user_id,)
            )

    def active_ids(self) -> list[int]:
        with self._conn() as conn:
            return [row[0] for row in conn.execute("SELECT id FROM users WHERE active = 1")]

    def deactivate(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))

    def count(self) -> tuple[int, int]:
        with self._conn() as conn:
            total, active = conn.execute("SELECT COUNT(*), COALESCE(SUM(active), 0) FROM users").fetchone()
            return total, active
