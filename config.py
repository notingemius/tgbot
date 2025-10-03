# D:\telegram_reminder_bot\config.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # опционально: .env тоже можно держать

DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "db.sqlite3"))

# Значения по умолчанию (из ENV / .env)
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL   = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Пытаемся перекрыть из локального файла с секретами
try:
    from config_secrets import (
        TELEGRAM_TOKEN   as S_TELEGRAM_TOKEN,
        CEREBRAS_API_KEY as S_CEREBRAS_API_KEY,
        CEREBRAS_MODEL   as S_CEREBRAS_MODEL,
        GEMINI_API_KEY   as S_GEMINI_API_KEY,
        GEMINI_MODEL     as S_GEMINI_MODEL,
    )
    TELEGRAM_TOKEN   = S_TELEGRAM_TOKEN   or TELEGRAM_TOKEN
    CEREBRAS_API_KEY = S_CEREBRAS_API_KEY or CEREBRAS_API_KEY
    CEREBRAS_MODEL   = S_CEREBRAS_MODEL   or CEREBRAS_MODEL
    GEMINI_API_KEY   = S_GEMINI_API_KEY   or GEMINI_API_KEY
    GEMINI_MODEL     = S_GEMINI_MODEL     or GEMINI_MODEL
except Exception:
    pass

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set (config_secrets.py or .env)")
