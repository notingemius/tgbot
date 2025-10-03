# D:\telegram_reminder_bot\utils\notes.py
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
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
CREATE INDEX IF NOT EXISTS idx_notes_status     ON notes(status);
CREATE INDEX IF NOT EXISTS idx_notes_snooze     ON notes(snooze_until);
"""

class NotesStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _ensure_schema(self):
        with self._connect() as con:
            con.executescript(_SCHEMA)

    # --- CRUD ---
    def add(self, user_id: int, chat_id: int, text: str) -> int:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty note text")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO notes (user_id, chat_id, text, status) VALUES (?, ?, ?, 'open')",
                (user_id, chat_id, text),
            )
            return cur.lastrowid

    def get(self, note_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            cur = con.execute(
                "SELECT id, user_id, chat_id, text, status, created_at, updated_at, snooze_until "
                "FROM notes WHERE id = ?",
                (note_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        keys = ["id","user_id","chat_id","text","status","created_at","updated_at","snooze_until"]
        return dict(zip(keys, row))

    def set_done(self, note_id: int):
        with self._connect() as con:
            con.execute(
                "UPDATE notes SET status='done', updated_at=CURRENT_TIMESTAMP, snooze_until=NULL WHERE id=?",
                (note_id,),
            )

    def keep_open(self, note_id: int):
        with self._connect() as con:
            con.execute(
                "UPDATE notes SET status='open', updated_at=CURRENT_TIMESTAMP, snooze_until=NULL WHERE id=?",
                (note_id,),
            )

    def snooze(self, note_id: int, minutes: int = 120):
        dt = datetime.utcnow() + timedelta(minutes=max(1, int(minutes)))
        with self._connect() as con:
            con.execute(
                "UPDATE notes SET status='snoozed', updated_at=CURRENT_TIMESTAMP, snooze_until=? WHERE id=?",
                (dt.strftime("%Y-%m-%d %H:%M:%S"), note_id),
            )

    def delete(self, note_id: int):
        with self._connect() as con:
            con.execute("DELETE FROM notes WHERE id=?", (note_id,))

    # --- Queries ---
    def list_pending(self, user_id: int, chat_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Показать «ожидающие» заметки: открытые + отложенные с истёкшим snooze.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT id, text, status, snooze_until, created_at
                  FROM notes
                 WHERE user_id=? AND chat_id=?
                   AND (
                         status='open'
                      OR (status='snoozed' AND (snooze_until IS NULL OR snooze_until<=?))
                   )
                 ORDER BY id ASC
                 LIMIT ?
                """,
                (user_id, chat_id, now, limit),
            )
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "status": r[2], "snooze_until": r[3], "created_at": r[4]} for r in rows]

    def list_open_all(self, user_id: int, chat_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT id, text, status, snooze_until, created_at
                  FROM notes
                 WHERE user_id=? AND chat_id=? AND status IN ('open','snoozed')
                 ORDER BY id ASC
                 LIMIT ?
                """,
                (user_id, chat_id, limit),
            )
            rows = cur.fetchall()
        return [{"id": r[0], "text": r[1], "status": r[2], "snooze_until": r[3], "created_at": r[4]} for r in rows]

    def list_due(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Заметки, по которым пришло время напоминания.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT id, user_id, chat_id, text, snooze_until
                  FROM notes
                 WHERE status='snoozed' AND snooze_until IS NOT NULL AND snooze_until<=?
                 ORDER BY snooze_until ASC
                 LIMIT ?
                """,
                (now, limit),
            )
            rows = cur.fetchall()
        return [{"id": r[0], "user_id": r[1], "chat_id": r[2], "text": r[3], "snooze_until": r[4]} for r in rows]

notes_store = NotesStore(DB_PATH)
