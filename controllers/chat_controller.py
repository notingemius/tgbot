"""
controllers/chat_controller.py

Simple controller that:
- tries local retriever (TF-IDF) first
- if not found or low score -> tries LLM (MistralService)
- on capacity/timeout -> optional HF fallback -> final friendly fallback
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# expects services/retriever_tfidf.py to expose search(query, top_k) -> list[dict] or list[tuple]
from services import retriever_tfidf

class ChatController:
    def __init__(self, llm_service=None, retriever_threshold: float = 0.35, llm_timeout: int = 18):
        """
        llm_service: instance of MistralService (or compatible)
        retriever_threshold: minimal score to accept local retrieval (0..1)
        llm_timeout: seconds to wait for LLM generation before timeout
        """
        self.llm = llm_service
        self.retriever_threshold = retriever_threshold
        self.llm_timeout = llm_timeout
        self._sem = asyncio.Semaphore(1)  # limit parallel LLM calls (protect free tier)

    async def respond(self, user_id: int, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Пустой запрос."

        # 1) Try retriever (fast)
        try:
            results = await asyncio.to_thread(retriever_tfidf.search, text, 3)
            if results:
                top = results[0]
                # support both dict and tuple results
                if isinstance(top, dict):
                    score = float(top.get("score", 0) or 0)
                    title = top.get("title") or ""
                    content = top.get("content") or ""
                else:
                    # tuple: (id, title, content, score)
                    score = float(top[3]) if len(top) > 3 else 0.0
                    title = top[1] if len(top) > 1 else ""
                    content = top[2] if len(top) > 2 else ""
                if score >= self.retriever_threshold:
                    snippet = content[:1000]
                    return f"Нашёл: {title}\n\n{snippet}"
        except Exception:
            logger.exception("Error in retriever_tfidf.search")

        # 2) Try LLM (Mistral). If not ready or in cooldown -> fallback quickly
        if self.llm and self.llm.is_ready():
            try:
                async with self._sem:
                    messages = [
                        {"role": "system", "content": "Ты полезный ассистент. Отвечай коротко и по делу."},
                        {"role": "user", "content": text}
                    ]
                    # call LLM; it returns str or None
                    reply = await asyncio.wait_for(
                        self.llm.chat(prompt=None, messages=messages, max_tokens=120, temperature=0.2),
                        timeout=self.llm_timeout
                    )
                    if reply:
                        return reply.strip()
                    logger.warning("LLM returned None (capacity/429 or other); will try fallback")
            except asyncio.TimeoutError:
                logger.warning("LLM generation timeout (user=%s)", user_id)
            except Exception:
                logger.exception("LLM call error")

            # try HF fallback if configured
            try:
                hf_resp = await self.llm.hf_fallback(text)
                if hf_resp:
                    return hf_resp.strip()
            except Exception:
                logger.exception("HF fallback error")

        # 3) Final fallback
        # offer useful local reply or user-friendly message
        try:
            # try one more local retrieval short snippet
            results = await asyncio.to_thread(retriever_tfidf.search, text, 1)
            if results:
                top = results[0]
                if isinstance(top, dict):
                    snippet = (top.get("content") or "")[:800]
                    title = top.get("title") or ""
                else:
                    snippet = top[2] if len(top) > 2 else ""
                    title = top[1] if len(top) > 1 else ""
                if snippet:
                    return f"Не удалось получить ответ от ИИ (перегрузка). Но я нашёл локально:\n\n{title}\n\n{snippet}"
        except Exception:
            logger.debug("Secondary local retrieval failed")

        return "Извини, ИИ сейчас недоступен (перегрузка). Попробуй повторить вопрос чуть позже."
