"""
Проста робота з SQLite без зайвих залежностей.
Зберігаємо: замовлення (orders) та відповіді на поля анкети (order_fields)
і file_id прикріплених файлів (order_files).
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH

STATUS_NEW = "new"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                user_full_name TEXT,
                category_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                answers_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )
        """)


def create_order(user_id: int, username: str | None, user_full_name: str, category_key: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, username, user_full_name, category_key, status, created_at, answers_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, user_full_name, category_key, STATUS_NEW,
             datetime.utcnow().isoformat(), json.dumps({})),
        )
        return cur.lastrowid


def save_answer(order_id: int, field_key: str, value: str):
    with get_conn() as conn:
        row = conn.execute("SELECT answers_json FROM orders WHERE id = ?", (order_id,)).fetchone()
        answers = json.loads(row["answers_json"]) if row else {}
        answers[field_key] = value
        conn.execute("UPDATE orders SET answers_json = ? WHERE id = ?", (json.dumps(answers), order_id))


def add_file(order_id: int, field_key: str, file_id: str, file_type: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO order_files (order_id, field_key, file_id, file_type) VALUES (?, ?, ?, ?)",
            (order_id, field_key, file_id, file_type),
        )


def get_order(order_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_order_files(order_id: int, field_key: str | None = None) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if field_key:
            return conn.execute(
                "SELECT * FROM order_files WHERE order_id = ? AND field_key = ?", (order_id, field_key)
            ).fetchall()
        return conn.execute("SELECT * FROM order_files WHERE order_id = ?", (order_id,)).fetchall()


def set_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def list_orders(status: str | None = None) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,)
            ).fetchall()
        return conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()


def list_orders_by_user(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
