import json
import sqlite3
from contextlib import contextmanager

from catalog import PRODUCTS_BY_ID, Product

STATUSES = {
    "new": "🆕 Нове",
    "confirmed": "✅ Підтверджено",
    "shipped": "🚚 Відправлено",
    "rejected": "❌ Скасовано",
}


class Database:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cart (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    qty INTEGER NOT NULL,
                    PRIMARY KEY (user_id, product_id)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    items TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
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

    def change_qty(self, user_id: int, product_id: int, delta: int) -> int:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO cart (user_id, product_id, qty) VALUES (?, ?, ?)
                ON CONFLICT (user_id, product_id) DO UPDATE SET qty = qty + excluded.qty
                """,
                (user_id, product_id, delta),
            )
            conn.execute("DELETE FROM cart WHERE qty <= 0")
            row = conn.execute(
                "SELECT qty FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id)
            ).fetchone()
            return row["qty"] if row else 0

    def cart(self, user_id: int) -> list[tuple[Product, int]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT product_id, qty FROM cart WHERE user_id = ?", (user_id,)).fetchall()
        return [(PRODUCTS_BY_ID[r["product_id"]], r["qty"]) for r in rows if r["product_id"] in PRODUCTS_BY_ID]

    def clear_cart(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))

    def create_order(self, user_id: int, items: list[tuple[Product, int]], name: str, phone: str, address: str) -> int:
        payload = json.dumps([{"name": p.name, "price": p.price, "qty": q} for p, q in items], ensure_ascii=False)
        total = sum(p.price * q for p, q in items)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO orders (user_id, items, total, name, phone, address) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, payload, total, name, phone, address),
            )
            conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            return cur.lastrowid

    def set_status(self, order_id: int, status: str) -> sqlite3.Row | None:
        with self._conn() as conn:
            conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    def recent_orders(self, limit: int = 10) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
