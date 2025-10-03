# services/cerebras_service.py
import asyncio
import logging
import traceback
from typing import Dict, List, Optional

from config import (
    CEREBRAS_API_KEY, CEREBRAS_MODEL,
    MAX_PAIRS, HARD_REPLY_LIMIT
)

try:
    from cerebras.cloud.sdk import Cerebras
except Exception as e:
    Cerebras = None

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Ти спілкуєшся українською, корисний асистент для чата Telegram. "
        "Відповідай коротко і по суті. "
        f"Обмежуй відповідь {HARD_REPLY_LIMIT} символами і не перевищуй, "
        "поки користувач явно не попросить більш розгорнуту відповідь словами "
        "\"подробнее\", \"разверни\", \"длинный\", \"full\", \"more\"."
    ),
}

def _extract_text_from_response(resp) -> str:
    try:
        if resp is None:
            return ""
        choices = getattr(resp, "choices", None)
        if choices and len(choices) > 0:
            first = choices[0]
            msg = getattr(first, "message", None)
            if msg and getattr(msg, "content", None):
                return msg.content
            d = getattr(first, "__dict__", {})
            if isinstance(d, dict):
                m = d.get("message")
                if isinstance(m, dict) and "content" in m:
                    return m["content"]
        outputs = getattr(resp, "outputs", None)
        if outputs and len(outputs) > 0:
            o = outputs[0]
            if isinstance(o, dict) and "content" in o:
                return o["content"]
            if hasattr(o, "content"):
                return o.content
        return str(resp)
    except Exception:
        logger.exception("extract_text_from_response failed")
        return "Error extracting text: " + traceback.format_exc()

def _wants_long_answer(user_prompt: str) -> bool:
    lp = (user_prompt or "").lower()
    markers = ("подробнее", "разверни", "длин", "full", "more")
    return any(m in lp for m in markers)

def _trim_history(messages: List[dict], max_pairs: int = MAX_PAIRS) -> List[dict]:
    if not messages:
        return messages
    limit = max_pairs * 2  # user+assistant
    if len(messages) <= limit:
        return messages
    return messages[-limit:]

def split_for_telegram(s: str, limit: int = 3500) -> List[str]:
    """Режем большой ответ на куски безопасно для Telegram (до 4096)."""
    s = (s or "").strip()
    if not s:
        return []
    chunks = []
    while len(s) > limit:
        cut = s.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(s[:cut].strip())
        s = s[cut:].strip()
    if s:
        chunks.append(s)
    return chunks

class CerebrasService:
    def __init__(self):
        self.client: Optional[Cerebras] = None
        self.dialogs: Dict[int, List[dict]] = {}  # chat_id -> list of {"role","content"}

    async def initialize(self) -> bool:
        if Cerebras is None:
            logger.error("cerebras-cloud-sdk не встановлено.")
            return False
        try:
            self.client = Cerebras(api_key=CEREBRAS_API_KEY)
            # простая «проверка жизни» — не делаем запрос, просто логируем
            logger.info("Cerebras client инициализирован.")
            return True
        except Exception:
            logger.exception("Не вдалося ініціалізувати Cerebras client")
            return False

    def is_ready(self) -> bool:
        return self.client is not None

    def reset_history(self, chat_id: int):
        self.dialogs[chat_id] = []

    def _ensure_history(self, chat_id: int):
        if chat_id not in self.dialogs:
            self.dialogs[chat_id] = []

    async def ask(self, chat_id: int, user_text: str) -> List[str]:
        """Главный метод: собирает историю, зовёт Cerebras, режет на чанки."""
        self._ensure_history(chat_id)
        msgs = [SYSTEM_PROMPT] + self.dialogs[chat_id] + [{"role": "user", "content": user_text}]
        msgs = _trim_history(msgs, MAX_PAIRS)

        if not self.client:
            return ["Извините, ИИ тимчасово недоступний."]

        try:
            # Cerebras — синхронный метод; завернём в to_thread
            def _call():
                return self.client.chat.completions.create(
                    messages=msgs,
                    model=CEREBRAS_MODEL,
                )
            resp = await asyncio.to_thread(_call)
            answer = _extract_text_from_response(resp) or "(пустой ответ)"

            # сохраняем историю
            self.dialogs[chat_id].append({"role": "user", "content": user_text})
            self.dialogs[chat_id].append({"role": "assistant", "content": answer})
            self.dialogs[chat_id] = _trim_history(self.dialogs[chat_id], MAX_PAIRS)

            # ограничение длины, если не просили «подробнее»
            if not _wants_long_answer(user_text):
                answer = answer.strip()
                if len(answer) > HARD_REPLY_LIMIT:
                    answer = answer[:HARD_REPLY_LIMIT].rstrip()

            return split_for_telegram(answer)

        except Exception:
            logger.exception("Cerebras API error")
            return ["Упс, Cerebras зараз недоступний. Спробуй ще раз пізніше."]
