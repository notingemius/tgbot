# D:\telegram_reminder_bot\utils\memory.py
import os
import sqlite3
from contextlib import closing
from typing import List, Literal, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

Role = Literal["user", "assistant"]  # system не храним в БД

# Настройки через ENV (есть разумные дефолты)
TTL_SECONDS = int(os.getenv("MEMORY_TTL_SECONDS", "7200"))          # 2 часа
MAX_MSG_PER_CHAT = int(os.getenv("MEMORY_MAX_MSG", "50"))           # сколько последних сообщений тянуть
MAX_CHARS = int(os.getenv("MEMORY_MAX_CHARS", "8000"))              # грубый токен-лимит по символам

# Путь к БД берём из config.DB_PATH
try:
    from config import DB_PATH
except Exception:
    # fallback — рядом с проектом
    DB_PATH = str(Path(__file__).resolve().parents[1] / "db.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_memory (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id  INTEGER NOT NULL,
  role     TEXT    NOT NULL CHECK(role IN ('user','assistant')),
  content  TEXT    NOT NULL,
  ts       DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_memory_chat_ts ON chat_memory(chat_id, ts);
"""

class _SQLiteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _ensure_schema(self):
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def add(self, chat_id: int, role: Role, content: str):
        with self._connect() as con:
            con.execute(
                "INSERT INTO chat_memory (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )

    def get_recent(self, chat_id: int, ttl_seconds: int, max_rows: int) -> List[Dict[str, Any]]:
        # Берём с запасом, потом отфильтруем по TTL и CHAR в Python
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT role, content, ts
                  FROM chat_memory
                 WHERE chat_id = ?
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (chat_id, max_rows * 2),
            )
            rows = cur.fetchall()

        # Фильтр по TTL (Python)
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
        msgs: List[Dict[str, Any]] = []
        for role, content, ts in rows:
            try:
                # ts в SQLite приходит как строка "YYYY-MM-DD HH:MM:SS"
                ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_dt = now
            if cutoff and ts_dt < cutoff:
                continue
            msgs.append({"role": role, "content": content, "ts": ts_dt})

        # Восстанавливаем хронологию (старые -> новые)
        msgs = list(reversed(msgs))
        return msgs[: max_rows * 2]

    def reset(self, chat_id: int):
        with self._connect() as con:
            con.execute("DELETE FROM chat_memory WHERE chat_id = ?", (chat_id,))

class Memory:
    def __init__(self, store: _SQLiteStore):
        self.store = store

    def add(self, chat_id: int, role: Role, content: str) -> None:
        content = (content or "").strip()
        if not content:
            return
        # защитимся от слишком больших кусков
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "…"
        self.store.add(chat_id, role, content)

    def get(self, chat_id: int) -> List[Dict[str, str]]:
        """
        Возвращаем историю для Cerebras в формате [{"role": "...", "content": "..."}]
        С резкой обрезкой по суммарной длине символов (грубая замена токен-лимита).
        """
        items = self.store.get_recent(chat_id, TTL_SECONDS, MAX_MSG_PER_CHAT)

        # Обрезаем по суммарным символам
        total = 0
        kept = []
        for m in reversed(items):  # пройдём от новых к старым, накапливая назад
            c = m["content"]
            l = len(c)
            if total + l > MAX_CHARS and kept:
                break
            total += l
            kept.append({"role": m["role"], "content": c})
        # Вернём в хронологии старые -> новые
        return list(reversed(kept)) if kept else []

    def reset(self, chat_id: int) -> None:
        self.store.reset(chat_id)

# Экземпляр памяти
memory = Memory(_SQLiteStore(DB_PATH))
