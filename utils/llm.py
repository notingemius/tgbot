# utils/llm.py
import re
import asyncio
from typing import List, Dict
from config import CEREBRAS_API_KEY, CEREBRAS_MODEL

__all__ = ["ask_cerebras"]

def _smart_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "\n", " "):
        p = cut.rfind(sep)
        if p >= int(limit * 0.6):
            return cut[:p+1].rstrip()
    return cut.rstrip() + "…"

def _call_sync(history: List[Dict], allow_long: bool, max_len: int, model_name: str) -> str:
    if not CEREBRAS_API_KEY:
        return "❗ CEREBRAS_API_KEY не задан."
    try:
        from cerebras.cloud.sdk import Cerebras  # требует пакет 'cerebras-cloud-sdk' в requirements.txt
    except Exception:
        return "⚠️ Cerebras SDK не установлен. Добавь 'cerebras-cloud-sdk' в requirements.txt или используй Gemini."

    try:
        client = Cerebras(api_key=CEREBRAS_API_KEY)
        stream = client.chat.completions.create(
            messages=history,
            model=model_name or CEREBRAS_MODEL,
            stream=True,
            max_completion_tokens=2000,
            temperature=0.7,
            top_p=0.9,
        )
        out_parts = []
        for chunk in stream:
            out_parts.append(chunk.choices[0].delta.content or "")
        out = "".join(out_parts).strip()
        out = re.sub(r"^(?:model|assistant)\s*:\s*", "", out, flags=re.I).strip()
        return out if allow_long else _smart_trim(out, max_len)
    except Exception as e:
        return f"⚠️ Cerebras error: {e}"

async def ask_cerebras(history: List[Dict], allow_long: bool, max_len: int = 600, model: str = "") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call_sync, history, allow_long, max_len, model or "")
