"""
services/mistral_service.py

Async-friendly wrapper around mistralai client with:
- cooldown circuit-breaker on 429 / "capacity exceeded"
- very small retry/backoff loop
- optional Hugging Face fallback (requires HF_API_TOKEN)
- returns `None` on unrecoverable failure so caller can fallback to retrieval/local response
"""
from __future__ import annotations
import os
import asyncio
import logging
import time
import random
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

try:
    from mistralai import Mistral
except Exception as e:
    Mistral = None
    logger.exception("mistralai import error: %s", e)

# optional HF fallback via requests
try:
    import requests
except Exception:
    requests = None
    logger.debug("requests not available; HF fallback disabled")


class MistralService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mistral-large-latest",
        cooldown_seconds: int = 90,
        max_retries: int = 1,
    ):
        """
        api_key: prefer env MISTRAL_API_KEY, or pass explicitly.
        cooldown_seconds: time to stay in cooldown after detecting capacity errors (seconds).
        max_retries: number of retries before entering cooldown (0..2).
        """
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.model = model
        self.client = None
        self.cooldown_seconds = cooldown_seconds
        self.max_retries = max_retries
        self._cooldown_until = 0.0

        if not Mistral:
            logger.error("mistralai library is unavailable; MistralService disabled.")
            return

        if not self.api_key:
            logger.warning("No MISTRAL_API_KEY provided; MistralService disabled.")
            return

        try:
            self.client = Mistral(api_key=self.api_key)
            logger.info("Mistral client initialized (model=%s)", model)
        except Exception:
            logger.exception("Failed to initialize Mistral client")
            self.client = None

    def is_ready(self) -> bool:
        """Consider ready if client exists and not in cooldown."""
        return bool(self.client) and (time.time() >= self._cooldown_until)

    def _enter_cooldown(self, reason: str):
        self._cooldown_until = time.time() + self.cooldown_seconds
        logger.warning("Entering Mistral cooldown for %ds: %s", self.cooldown_seconds, reason)

    async def chat(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 120,
        temperature: float = 0.2,
    ) -> Optional[str]:
        """
        Call Mistral chat endpoint. Returns string on success or None on failure.
        Uses a short retry/backoff, and enters cooldown on repeated 429/capacity.
        - messages: list of {"role":..., "content":...} (preferred for chat)
        - If messages is None, a simple user prompt is built.
        """
        if not self.client:
            return None

        now = time.time()
        if now < self._cooldown_until:
            logger.info("Mistral in cooldown (%.1fs remaining)", self._cooldown_until - now)
            return None

        msgs = messages if messages is not None else [{"role": "user", "content": prompt or ""}]

        def _sync_call():
            # minimal retries; if 429/capacity occurs -> cooldown
            for attempt in range(self.max_retries + 1):
                try:
                    resp = self.client.chat.complete(
                        model=self.model,
                        messages=msgs,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    # try structured extraction
                    try:
                        return resp.choices[0].message.content
                    except Exception:
                        # fallback to dictionary-style
                        if isinstance(resp, dict):
                            return resp.get("text") or resp.get("content") or str(resp)
                        return str(resp)
                except Exception as e:
                    s = str(e).lower()
                    # handle capacity / 429 heuristically
                    if "429" in s or "too many requests" in s or "capacity" in s or "service tier capacity" in s:
                        if attempt >= self.max_retries:
                            # go to cooldown
                            self._enter_cooldown("429/capacity")
                            return None
                        backoff = (2 ** attempt) + random.random()
                        logger.warning("Mistral 429/capacity (attempt %d). Backing off %.1fs", attempt + 1, backoff)
                        time.sleep(backoff)
                        continue
                    # other errors: log and abort
                    logger.exception("Mistral API error: %s", e)
                    return None
            return None

        return await asyncio.to_thread(_sync_call)

    async def embeddings(self, texts: List[str], model: str = "mistral-embed"):
        if not self.client:
            raise RuntimeError("Mistral client not initialized")
        def _sync_embeddings():
            return self.client.embeddings.create(model=model, inputs=texts)
        return await asyncio.to_thread(_sync_embeddings)

    # Optional HF fallback (requires HF_API_TOKEN in env). Returns string or None.
    async def hf_fallback(self, prompt: str, model: str = "gpt2"):
        if not requests:
            return None
        hf_token = os.getenv("HF_API_TOKEN")
        if not hf_token:
            return None
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {"inputs": prompt, "options": {"wait_for_model": True}}
        def _sync_hf():
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=20)
                r.raise_for_status()
                out = r.json()
                # typical HF output: list with generated_text
                if isinstance(out, list) and len(out) > 0:
                    return out[0].get("generated_text") or out[0].get("text") or str(out[0])
                if isinstance(out, dict):
                    return out.get("generated_text") or out.get("text") or str(out)
                return str(out)
            except Exception:
                logger.exception("HF fallback failed")
                return None
        return await asyncio.to_thread(_sync_hf)
