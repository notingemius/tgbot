import re
import asyncio
from typing import List, Dict
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

# Инициализируем клиент один раз
_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def _smart_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "\n", " "):
        p = cut.rfind(sep)
        if p >= int(limit * 0.6):
            return cut[:p+1].rstrip()
    return cut.rstrip() + "…"

def _history_to_prompt(history: List[Dict], model_name: str) -> str:
    """
    Превращаем историю в один текст (совместимо с любыми версиями google-genai).
    """
    lines = [
        f"[system] Ты — Gemini (Google), модель {model_name}. "
        "Отвечай кратко (≤500 символов), если явно не попросили подробно. "
        "Если спрашивают, какая ты модель — отвечай точным названием Gemini."
    ]
    for m in history:
        role = "user" if m.get("role") == "user" else "assistant"
        content = (m.get("content") or "").strip()
        lines.append(f"[{role}] {content}")
    # Подсказываем, что сейчас должен говорить ассистент
    lines.append("[assistant]")
    return "\n".join(lines)

def _call_sync(history: List[Dict], allow_long: bool, max_len: int, model_name: str) -> str:
    if not _client:
        return "❗ GEMINI_API_KEY не задан (config_secrets.py / .env)."

    model = model_name or GEMINI_MODEL or "gemini-2.5-flash"
    try:
        prompt = _history_to_prompt(history, model)
        resp = _client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        out = (getattr(resp, "text", "") or "").strip()
        # На всякий случай убираем возможные префиксы
        out = re.sub(r"^(?:model|assistant)\s*:\s*", "", out, flags=re.I).strip()
        return out if allow_long else _smart_trim(out, max_len)
    except Exception as e:
        return f"⚠️ Gemini error: {e}"

async def ask_gemini(history: List[Dict], allow_long: bool, max_len: int = 500, model: str = None) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call_sync, history, allow_long, max_len, model or "")
