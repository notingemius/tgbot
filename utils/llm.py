# D:\telegram_reminder_bot\utils\llm.py
import re
import aiohttp
from typing import List, Optional, Dict
from config import CEREBRAS_API_KEY, CEREBRAS_MODEL

API_URL = "https://api.cerebras.ai/v1/chat/completions"
SYSTEM_PROMPT = "Отвечай кратко. По умолчанию не более 500 символов, если явно не попросили подробно."

def _smart_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in [". ", "! ", "? ", "\n", " "]:
        p = cut.rfind(sep)
        if p >= int(limit * 0.6):
            return cut[:p+1].rstrip()
    return cut.rstrip() + "…"

async def ask_ai(
    prompt: Optional[str] = None,
    *,
    history: Optional[List[Dict]] = None,
    allow_long: bool = False,
    max_len: int = 500,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    if not CEREBRAS_API_KEY:
        return "❗ Не задан CEREBRAS_API_KEY (config_secrets.py / .env)."

    model = model or CEREBRAS_MODEL
    system_prompt = system_prompt or SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    elif prompt:
        messages.append({"role": "user", "content": prompt})
    else:
        return "❗ Пустой запрос."

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048 if allow_long else 512,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(API_URL, headers={
                "Authorization": f"Bearer {CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            }, json=payload, timeout=90) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    return f"⚠️ API error {resp.status}: {txt[:400]}"
                data = await resp.json()
    except Exception as e:
        return f"⚠️ Ошибка запроса к ИИ: {e}"

    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return content.strip() if allow_long else _smart_trim(content.strip(), max_len)
