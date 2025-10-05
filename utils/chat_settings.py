# utils/chat_settings.py
import sqlite3
from typing import Optional
from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id    INTEGER PRIMARY KEY,
  ai_engine  TEXT NOT NULL DEFAULT 'gemini',
  language   TEXT NOT NULL DEFAULT 'ru',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

class ChatSettings:
    def __init__(self, path: str):
        self.path = path
        with sqlite3.connect(self.path) as con:
            con.executescript(_SCHEMA)

    def _con(self):
        return sqlite3.connect(self.path, timeout=30, check_same_thread=False)

    def set_ai(self, chat_id: int, ai: str):
        ai = ai.lower().strip()
        if ai not in ("cerebras","gemini"):
            ai = "gemini"
        with self._con() as con:
            con.execute("""
                INSERT INTO chat_settings(chat_id, ai_engine) VALUES(?,?)
                ON CONFLICT(chat_id) DO UPDATE SET ai_engine=excluded.ai_engine, updated_at=CURRENT_TIMESTAMP
            """, (chat_id, ai))

    def get_ai(self, chat_id: int) -> Optional[str]:
        with self._con() as con:
            cur = con.execute("SELECT ai_engine FROM chat_settings WHERE chat_id=?", (chat_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_lang(self, chat_id: int, lang: str):
        lang = "uk" if (lang or "").lower().startswith("uk") else "ru"
        with self._con() as con:
            con.execute("""
                INSERT INTO chat_settings(chat_id, language) VALUES(?,?)
                ON CONFLICT(chat_id) DO UPDATE SET language=excluded.language, updated_at=CURRENT_TIMESTAMP
            """, (chat_id, lang))

    def get_lang(self, chat_id: int) -> str:
        with self._con() as con:
            cur = con.execute("SELECT language FROM chat_settings WHERE chat_id=?", (chat_id,))
            row = cur.fetchone()
            return (row[0] if row else "ru")

chat_settings = ChatSettings(DB_PATH)
