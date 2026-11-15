"""Shared memory: a small SQLite store every skill reads and writes."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


class State:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ts REAL)")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS reminders "
                "(id INTEGER PRIMARY KEY, due REAL, text TEXT, done INTEGER DEFAULT 0)"
            )

    # shared context ----------------------------------------------------
    def set(self, key: str, value) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO kv VALUES (?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, ts=excluded.ts",
                (key, json.dumps(value), time.time()),
            )

    def get(self, key: str, default=None):
        with self._lock:
            row = self._db.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def snapshot(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT k, v FROM kv").fetchall()
        return {k: json.loads(v) for k, v in rows}

    # reminders ---------------------------------------------------------
    def add_reminder(self, due: float, text: str) -> int:
        with self._lock, self._db:
            return self._db.execute("INSERT INTO reminders (due, text) VALUES (?,?)", (due, text)).lastrowid

    def pending_reminders(self) -> list[tuple[int, float, str]]:
        with self._lock:
            return self._db.execute("SELECT id, due, text FROM reminders WHERE done=0 ORDER BY due").fetchall()

    def take_due_reminders(self, now: float) -> list[tuple[int, float, str]]:
        with self._lock, self._db:
            rows = self._db.execute("SELECT id, due, text FROM reminders WHERE done=0 AND due<=?", (now,)).fetchall()
            self._db.executemany("UPDATE reminders SET done=1 WHERE id=?", [(r[0],) for r in rows])
        return rows

    def cancel_reminder(self, reminder_id: int) -> bool:
        with self._lock, self._db:
            return self._db.execute("UPDATE reminders SET done=1 WHERE id=? AND done=0", (reminder_id,)).rowcount > 0
