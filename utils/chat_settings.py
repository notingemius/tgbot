# D:\telegram_reminder_bot\utils\chat_settings.py
import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime
from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id    INTEGER PRIMARY KEY,
  ai_engine  TEXT NOT NULL CHECK(ai_engine IN ('cerebras','gemini')),
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

class ChatSettings:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _ensure_schema(self):
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def set_ai(self, chat_id: int, ai: str):
        ai = ai.lower()
        if ai not in ("cerebras", "gemini"):
            raise ValueError("ai must be 'cerebras' or 'gemini'")
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO chat_settings (chat_id, ai_engine, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET ai_engine=excluded.ai_engine, updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, ai)
            )

    def get_ai(self, chat_id: int) -> Optional[str]:
        with self._connect() as con:
            cur = con.execute("SELECT ai_engine FROM chat_settings WHERE chat_id = ?", (chat_id,))
            row = cur.fetchone()
            return row[0] if row else None

chat_settings = ChatSettings(DB_PATH)
