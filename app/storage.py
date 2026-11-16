"""Tiny SQLite history store (standard library only)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any

from . import config


@contextmanager
def _conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                doc_type TEXT, preview TEXT, source_text TEXT, result_json TEXT)"""
        )


def save(text: str, result: dict[str, Any]) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO extractions (doc_type, preview, source_text, result_json) VALUES (?,?,?,?)",
            (result.get("document_type", ""), text.strip()[:80], text, json.dumps(result, ensure_ascii=False)),
        )
        return int(cur.lastrowid)


def list_items(limit: int = 30) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, created_at, doc_type, preview FROM extractions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get(item_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        r = con.execute("SELECT * FROM extractions WHERE id = ?", (item_id,)).fetchone()
        if not r:
            return None
        return {"id": r["id"], "created_at": r["created_at"], "text": r["source_text"], "result": json.loads(r["result_json"])}


def delete(item_id: int) -> bool:
    with _conn() as con:
        return con.execute("DELETE FROM extractions WHERE id = ?", (item_id,)).rowcount > 0
