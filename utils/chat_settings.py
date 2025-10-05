# D:\telegram_reminder_bot\utils\chat_settings.py
import os
import sqlite3
from typing import Optional
from config import DB_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id    BIGINT PRIMARY KEY,
  ai_engine  VARCHAR(16) NOT NULL CHECK(ai_engine IN ('cerebras','gemini')),
  language   VARCHAR(4)  NOT NULL DEFAULT 'ru',
  updated_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id    INTEGER PRIMARY KEY,
  ai_engine  TEXT NOT NULL CHECK(ai_engine IN ('cerebras','gemini')),
  language   TEXT NOT NULL DEFAULT 'ru',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

class ChatSettings:
    def __init__(self, dsn: str | None = None, sqlite_path: str | None = None):
        self.dsn = dsn
        self.sqlite_path = sqlite_path
        self.pg = None
        if self.dsn:
            try:
                import psycopg2  # type: ignore
                self.pg = psycopg2
            except Exception:
                self.pg = None
        self._ensure_schema()

    # ---------- PG ----------
    def _pg_conn(self):
        return self.pg.connect(self.dsn)  # type: ignore

    def _pg_exec(self, sql: str, params: tuple = ()):
        with self._pg_conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, params)

    def _pg_query_one(self, sql: str, params: tuple):
        with self._pg_conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row[0] if row else None

    # ---------- SQLite ----------
    def _sq_conn(self):
        return sqlite3.connect(self.sqlite_path, timeout=30, check_same_thread=False)

    def _sq_exec(self, sql: str, params: tuple = ()):
        with self._sq_conn() as con:
            con.execute(sql, params)

    def _sq_query_one(self, sql: str, params: tuple):
        with self._sq_conn() as con:
            cur = con.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None

    # ---------- Common ----------
    def _ensure_schema(self):
        if self.pg:
            with self._pg_conn() as con:
                with con.cursor() as cur:
                    cur.execute(_SCHEMA_PG)
        else:
            with self._sq_conn() as con:
                con.executescript(_SCHEMA_SQLITE)

    def set_ai(self, chat_id: int, ai: str):
        ai = (ai or "").lower().strip()
        if ai not in ("cerebras", "gemini"):
            raise ValueError("ai must be 'cerebras' or 'gemini'")
        if self.pg:
            self._pg_exec(
                """
                INSERT INTO chat_settings (chat_id, ai_engine)
                VALUES (%s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET ai_engine=EXCLUDED.ai_engine, updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, ai),
            )
        else:
            self._sq_exec(
                """
                INSERT INTO chat_settings (chat_id, ai_engine)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET ai_engine=excluded.ai_engine, updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, ai),
            )

    def get_ai(self, chat_id: int) -> Optional[str]:
        if self.pg:
            return self._pg_query_one("SELECT ai_engine FROM chat_settings WHERE chat_id=%s", (chat_id,))
        return self._sq_query_one("SELECT ai_engine FROM chat_settings WHERE chat_id=?", (chat_id,))

    def set_lang(self, chat_id: int, lang: str):
        lang = (lang or "ru").lower().strip()
        if lang not in ("ru", "uk"):
            lang = "ru"
        if self.pg:
            self._pg_exec(
                """
                INSERT INTO chat_settings (chat_id, language, ai_engine)
                VALUES (%s, %s, COALESCE((SELECT ai_engine FROM chat_settings WHERE chat_id=%s),'gemini'))
                ON CONFLICT (chat_id) DO UPDATE SET language=EXCLUDED.language, updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, lang, chat_id),
            )
        else:
            self._sq_exec(
                """
                INSERT INTO chat_settings (chat_id, language, ai_engine)
                VALUES (?, ?, COALESCE((SELECT ai_engine FROM chat_settings WHERE chat_id=?),'gemini'))
                ON CONFLICT(chat_id) DO UPDATE SET language=excluded.language, updated_at=CURRENT_TIMESTAMP
                """,
                (chat_id, lang, chat_id),
            )

    def get_lang(self, chat_id: int) -> str:
        if self.pg:
            val = self._pg_query_one("SELECT language FROM chat_settings WHERE chat_id=%s", (chat_id,))
        else:
            val = self._sq_query_one("SELECT language FROM chat_settings WHERE chat_id=?", (chat_id,))
        return val or "ru"

chat_settings = ChatSettings(
    dsn=DATABASE_URL if DATABASE_URL else None,
    sqlite_path=DB_PATH,
)
