# D:\telegram_reminder_bot\utils\daily.py
import os
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from config import DB_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS daily_tasks (
  id           SERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL,
  chat_id      BIGINT NOT NULL,
  text         TEXT   NOT NULL,
  last_done    DATE,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_daily_user_chat ON daily_tasks(user_id, chat_id);
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS daily_tasks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  chat_id      INTEGER NOT NULL,
  text         TEXT    NOT NULL,
  last_done    DATE,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_daily_user_chat ON daily_tasks(user_id, chat_id);
"""

def today() -> date:
    return datetime.utcnow().date()

class _PGDaily:
    def __init__(self, dsn: str):
        import psycopg2  # type: ignore
        self.pg = psycopg2
        self.dsn = dsn
        self._ensure()

    def _con(self):
        return self.pg.connect(self.dsn)

    def _ensure(self):
        with self._con() as con, con.cursor() as cur:
            cur.execute(_SCHEMA_PG)

    def add(self, user_id: int, chat_id: int, text: str) -> int:
        with self._con() as con, con.cursor() as cur:
            cur.execute(
                "INSERT INTO daily_tasks (user_id, chat_id, text) VALUES (%s,%s,%s) RETURNING id",
                (user_id, chat_id, text),
            )
            return cur.fetchone()[0]

    def list(self, user_id: int, chat_id: int) -> List[Dict[str, Any]]:
        with self._con() as con, con.cursor() as cur:
            cur.execute(
                "SELECT id, text, last_done FROM daily_tasks WHERE user_id=%s AND chat_id=%s ORDER BY id ASC",
                (user_id, chat_id),
            )
            rows = cur.fetchall()
        out = []
        td = today()
        for r in rows:
            ld = r[2]
            out.append({"id": r[0], "text": r[1], "done_today": (ld == td)})
        return out

    def mark_done(self, task_id: int):
        with self._con() as con, con.cursor() as cur:
            cur.execute("UPDATE daily_tasks SET last_done=CURRENT_DATE WHERE id=%s", (task_id,))

    def delete(self, task_id: int):
        with self._con() as con, con.cursor() as cur:
            cur.execute("DELETE FROM daily_tasks WHERE id=%s", (task_id,))

class _SQDaily:
    def __init__(self, path: str):
        self.path = path
        self._ensure()

    def _con(self):
        return sqlite3.connect(self.path, timeout=30, check_same_thread=False)

    def _ensure(self):
        with self._con() as con:
            con.executescript(_SCHEMA_SQLITE)

    def add(self, user_id: int, chat_id: int, text: str) -> int:
        with self._con() as con:
            cur = con.execute(
                "INSERT INTO daily_tasks (user_id, chat_id, text) VALUES (?,?,?)",
                (user_id, chat_id, text),
            )
            return cur.lastrowid

    def list(self, user_id: int, chat_id: int) -> List[Dict[str, Any]]:
        with self._con() as con:
            cur = con.execute(
                "SELECT id, text, last_done FROM daily_tasks WHERE user_id=? AND chat_id=? ORDER BY id ASC",
                (user_id, chat_id),
            )
            rows = cur.fetchall()
        out = []
        td = today().isoformat()
        for r in rows:
            ld = r[2]
            out.append({"id": r[0], "text": r[1], "done_today": (ld == td)})
        return out

    def mark_done(self, task_id: int):
        with self._con() as con:
            con.execute("UPDATE daily_tasks SET last_done=DATE('now') WHERE id=?", (task_id,))

    def delete(self, task_id: int):
        with self._con() as con:
            con.execute("DELETE FROM daily_tasks WHERE id=?", (task_id,))

class Daily:
    def __init__(self):
        if DATABASE_URL:
            self.impl = _PGDaily(DATABASE_URL)
            print("[daily] Using PostgreSQL backend")
        else:
            self.impl = _SQDaily(DB_PATH)
            print("[daily] Using SQLite backend")

    def add(self, *a, **kw): return self.impl.add(*a, **kw)
    def list(self, *a, **kw): return self.impl.list(*a, **kw)
    def mark_done(self, *a, **kw): return self.impl.mark_done(*a, **kw)
    def delete(self, *a, **kw): return self.impl.delete(*a, **kw)

daily_store = Daily()
