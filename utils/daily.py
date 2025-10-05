# utils/daily.py
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_tasks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  chat_id    INTEGER NOT NULL,
  text       TEXT    NOT NULL,
  last_done  DATE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_daily_user_chat ON daily_tasks(user_id, chat_id);
"""

def _con():
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)

with _con() as con:
    con.executescript(_SCHEMA)

def add(user_id: int, chat_id: int, text: str) -> int:
    with _con() as con:
        cur = con.execute("INSERT INTO daily_tasks (user_id, chat_id, text) VALUES (?,?,?)",
                          (user_id, chat_id, text))
        return cur.lastrowid

def list(user_id: int, chat_id: int) -> List[Dict[str, Any]]:
    with _con() as con:
        cur = con.execute("SELECT id, text, last_done FROM daily_tasks WHERE user_id=? AND chat_id=? ORDER BY id ASC",
                          (user_id, chat_id))
        rows = cur.fetchall()
    today = datetime.utcnow().date().isoformat()
    out = []
    for r in rows:
        out.append({"id": r[0], "text": r[1], "done_today": (r[2] == today)})
    return out

def mark_done(task_id: int):
    with _con() as con:
        con.execute("UPDATE daily_tasks SET last_done=DATE('now') WHERE id=?", (task_id,))

def delete(task_id: int):
    with _con() as con:
        con.execute("DELETE FROM daily_tasks WHERE id=?", (task_id,))
