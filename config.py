# config.py
import os

# ==== токены ====
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "").strip()

# AI
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL   = os.getenv("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507").strip()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# ==== вебхук/рендер ====
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_PATH   = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CRON_SECRET    = os.getenv("CRON_SECRET", "")
DISABLE_BOT    = os.getenv("DISABLE_BOT", "0") == "1"
DISABLE_LOOP   = os.getenv("DISABLE_LOOP", "1") == "1"  # на free лучше через /cron/tick
PORT           = int(os.getenv("PORT", "10000"))

# ==== файлы/БД ====
DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
