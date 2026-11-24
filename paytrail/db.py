"""SQLite storage for receipts."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id            TEXT PRIMARY KEY,   -- Gmail Message-ID (or sample id)
    nickname      TEXT NOT NULL,
    payee         TEXT,
    amount        REAL,
    currency      TEXT,
    paid_on       TEXT,               -- YYYY-MM-DD
    category      TEXT,
    is_subscription INTEGER DEFAULT 0,
    billing_period TEXT,
    summary       TEXT,
    subject       TEXT,
    sender        TEXT,
    email_date    TEXT,
    attachments   TEXT,               -- JSON list of file names
    gmail_link    TEXT,
    source        TEXT,               -- 'gmail' or 'sample'
    embedding     TEXT                -- JSON list of floats, may be NULL
);
"""

FIELDS = [
    "id", "nickname", "payee", "amount", "currency", "paid_on", "category",
    "is_subscription", "billing_period", "summary", "subject", "sender",
    "email_date", "attachments", "gmail_link", "source", "embedding",
]


@contextmanager
def connect(path: Path | None = None):
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _to_row(r: dict) -> tuple:
    r = dict(r)
    if isinstance(r.get("attachments"), list):
        r["attachments"] = json.dumps(r["attachments"])
    if isinstance(r.get("embedding"), list):
        r["embedding"] = json.dumps(r["embedding"])
    r["is_subscription"] = 1 if r.get("is_subscription") else 0
    return tuple(r.get(f) for f in FIELDS)


def upsert(receipts: list[dict], path: Path | None = None) -> int:
    if not receipts:
        return 0
    placeholders = ",".join("?" for _ in FIELDS)
    with connect(path) as conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO receipts ({','.join(FIELDS)}) VALUES ({placeholders})",
            [_to_row(r) for r in receipts],
        )
    return len(receipts)


def existing_ids(path: Path | None = None) -> set[str]:
    with connect(path) as conn:
        return {row["id"] for row in conn.execute("SELECT id FROM receipts")}


def _from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("attachments", "embedding"):
        try:
            d[key] = json.loads(d[key]) if d.get(key) else ([] if key == "attachments" else None)
        except (TypeError, ValueError):
            d[key] = [] if key == "attachments" else None
    d["is_subscription"] = bool(d.get("is_subscription"))
    return d


def all_receipts(path: Path | None = None) -> list[dict]:
    with connect(path) as conn:
        rows = conn.execute("SELECT * FROM receipts ORDER BY paid_on DESC").fetchall()
    return [_from_row(r) for r in rows]


def get(receipt_id: str, path: Path | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    return _from_row(row) if row else None


def rename(receipt_id: str, nickname: str, path: Path | None = None) -> bool:
    with connect(path) as conn:
        cur = conn.execute("UPDATE receipts SET nickname = ? WHERE id = ?", (nickname.strip(), receipt_id))
    return cur.rowcount > 0


def clear(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute("DELETE FROM receipts")
