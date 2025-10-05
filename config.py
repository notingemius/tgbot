# config.py
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from runpy import run_path

# ---------- 1) .env локальный ----------
load_dotenv(find_dotenv())

# ---------- 2) .env из Secret Files ----------
SECRETS_DIR  = os.getenv("SECRETS_DIR", "/etc/secrets")
SECRETS_FILE = os.getenv("SECRETS_FILE", "")  # путь к .env (по желанию)

def _load_env_file(path: Path):
    if path.exists():
        load_dotenv(path, override=True)

# попробуем явный .env
if SECRETS_FILE:
    _load_env_file(Path(SECRETS_FILE))
else:
    d = Path(SECRETS_DIR)
    if d.is_dir():
        for name in (".env", "env", "secrets.env"):
            _load_env_file(d / name)

# ---------- 3) Python-файл из Secret Files ----------
SECRETS_PY = os.getenv("SECRETS_PY", str(Path(SECRETS_DIR) / "config_secrets.py"))

def _load_py_secrets(py_path: Path):
    if not py_path.exists():
        return
    try:
        data = run_path(str(py_path))  # исполняем как модуль и получаем dict переменных
        for k, v in data.items():
            if not k.isupper():
                continue
            # Не перезаписываем то, что уже явно задано в окружении
            if k in os.environ:
                continue
            if isinstance(v, (str, int, float, bool)):
                os.environ[k] = str(v)
    except Exception:
        # тихо игнорируем, чтобы не мешать запуску
        pass

_load_py_secrets(Path(SECRETS_PY))

# ---------- Достаём значения ----------
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "").strip()

# AI
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL   = os.getenv("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507").strip()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Webhook / Render
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_PATH   = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CRON_SECRET    = os.getenv("CRON_SECRET", "")
DISABLE_BOT    = os.getenv("DISABLE_BOT", "0") == "1"
DISABLE_LOOP   = os.getenv("DISABLE_LOOP", "1") == "1"
PORT           = int(os.getenv("PORT", "10000"))

# DB
DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
