# utils/notes.py
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any
from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  chat_id      INTEGER NOT NULL,
  text         TEXT    NOT NULL,
  status       TEXT    NOT NULL CHECK(status IN ('open','done','snoozed')),
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  snooze_until DATETIME
);
CREATE INDEX IF NOT EXISTS idx_notes_user_chat ON notes(user_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);
CREATE INDEX IF NOT EXISTS idx_notes_snooze ON notes(snooze_until);
"""

def _con():
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    return con

with _con() as con:
    con.executescript(_SCHEMA)

def add(user_id: int, chat_id: int, text: str) -> int:
    with _con() as con:
        cur = con.execute(
            "INSERT INTO notes (user_id, chat_id, text, status) VALUES (?,?,?, 'open')",
            (user_id, chat_id, text),
        )
        return cur.lastrowid

def set_done(note_id: int):
    with _con() as con:
        con.execute(
            "UPDATE notes SET status='done', updated_at=CURRENT_TIMESTAMP, snooze_until=NULL WHERE id=?",
            (note_id,),
        )

def keep_open(note_id: int):
    with _con() as con:
        con.execute(
            "UPDATE notes SET status='open', updated_at=CURRENT_TIMESTAMP, snooze_until=NULL WHERE id=?",
            (note_id,),
        )

def snooze(note_id: int, minutes: int):
    dt = datetime.utcnow() + timedelta(minutes=max(1, int(minutes)))
    with _con() as con:
        con.execute(
            "UPDATE notes SET status='snoozed', updated_at=CURRENT_TIMESTAMP, snooze_until=? WHERE id=?",
            (dt.strftime("%Y-%m-%d %H:%M:%S"), note_id),
        )

def delete(note_id: int):
    with _con() as con:
        con.execute("DELETE FROM notes WHERE id=?", (note_id,))

def list_open_all(user_id: int, chat_id: int, limit: int) -> List[Dict[str, Any]]:
    with _con() as con:
        cur = con.execute(
            """
            SELECT id, text, status, snooze_until, created_at
              FROM notes
             WHERE user_id=? AND chat_id=? AND status IN ('open','snoozed')
             ORDER BY id ASC
             LIMIT ?
            """, (user_id, chat_id, limit)
        )
        rows = cur.fetchall()
    return [{"id": r[0], "text": r[1], "status": r[2], "snooze_until": r[3], "created_at": r[4]} for r in rows]

def list_pending(user_id: int, chat_id: int, limit: int) -> List[Dict[str, Any]]:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with _con() as con:
        cur = con.execute(
            """
            SELECT id, text, status, snooze_until, created_at
              FROM notes
             WHERE user_id=? AND chat_id=?
               AND (status='open' OR (status='snoozed' AND (snooze_until IS NULL OR snooze_until<=?)))
             ORDER BY id ASC
             LIMIT ?
            """, (user_id, chat_id, now, limit)
        )
        rows = cur.fetchall()
    return [{"id": r[0], "text": r[1], "status": r[2], "snooze_until": r[3], "created_at": r[4]} for r in rows]

def list_due(limit: int) -> List[Dict[str, Any]]:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with _con() as con:
        cur = con.execute(
            """
            SELECT id, user_id, chat_id, text, snooze_until
              FROM notes
             WHERE status='snoozed' AND snooze_until IS NOT NULL AND snooze_until<=?
             ORDER BY snooze_until ASC
             LIMIT ?
            """, (now, limit)
        )
        rows = cur.fetchall()
    return [{"id": r[0], "user_id": r[1], "chat_id": r[2], "text": r[3], "snooze_until": r[4]} for r in rows]

# удобная фасада
class _NotesFacade:
    add = staticmethod(add)
    set_done = staticmethod(set_done)
    keep_open = staticmethod(keep_open)
    snooze = staticmethod(snooze)
    delete = staticmethod(delete)
    list_open_all = staticmethod(list_open_all)
    list_pending = staticmethod(list_pending)
    list_due = staticmethod(list_due)

notes_store = _NotesFacade()
