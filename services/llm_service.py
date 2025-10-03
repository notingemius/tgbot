# services/llm_service.py
import os
import logging
import asyncio
from pathlib import Path
from config import MODELS_DIR, MODEL_NAME

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
    _HAS_LLAMA = True
except Exception:
    Llama = None
    _HAS_LLAMA = False

class LLMService:
    def __init__(self, model_name: str = None, model_dir: str = None, n_ctx: int = 1024, n_threads: int = 2):
        self.model_name = model_name or MODEL_NAME
        self.model_dir = model_dir or MODELS_DIR
        self.n_ctx = n_ctx
        self.n_threads = n_threads or int(os.environ.get("OMP_NUM_THREADS", "2"))
        self.model = None
        self._lock = asyncio.Lock()           # <- ключевая защита от параллельных вызовов
        self._reinit_scheduled = False

    def _init_model_sync(self):
        """Синхронная инициализация (выполняется в to_thread)"""
        if not _HAS_LLAMA:
            raise RuntimeError("llama_cpp not installed")
        model_path = Path(self.model_dir) / self.model_name
        if not model_path.exists():
            raise FileNotFoundError(f"LLM model file not found: {model_path}")
        os.environ["OMP_NUM_THREADS"] = str(self.n_threads)
        logger.info("Initializing Llama model (sync): %s", model_path)
        # Создаём экземпляр (может бросить исключение)
        model = Llama(model_path=str(model_path), n_ctx=self.n_ctx)
        return model

    async def initialize(self) -> bool:
        """Асинхронная обёртка для инициализации модели"""
        try:
            self.model = await asyncio.to_thread(self._init_model_sync)
            logger.info("LLM loaded, n_ctx=%s, threads=%s", self.n_ctx, self.n_threads)
            self._reinit_scheduled = False
            return True
        except Exception as e:
            logger.exception("Ошибка загрузки LLM: %s", e)
            return False

    def is_ready(self) -> bool:
        return self.model is not None

    async def _reinit_async(self):
        """Попытка реинициализировать модель в фоне (однократно)"""
        if self._reinit_scheduled:
            return
        self._reinit_scheduled = True
        logger.info("Scheduling LLM re-initialization...")
        try:
            ok = await self.initialize()
            if ok:
                logger.info("LLM reinitialized successfully.")
            else:
                logger.warning("LLM reinit failed.")
        except Exception:
            logger.exception("Error during async reinit.")

    async def generate_response(self, prompt: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
        """Генерация ответа (безопасно, сериализовано)"""
        if not self.is_ready():
            return "Извините, LLM временно недоступна."

        # Сериализуем все вызовы к self.model
        async with self._lock:
            loop = asyncio.get_running_loop()
            def _sync():
                # синхронный вызов Llama — выполняется в thread pool
                try:
                    out = self.model(prompt, max_tokens=max_tokens, temperature=temperature)
                    if isinstance(out, dict) and "choices" in out and out["choices"]:
                        return out["choices"][0].get("text") or str(out["choices"][0])
                    return str(out)
                except Exception as e:
                    # пробросим исключение наружу для логики ниже
                    raise

            try:
                result = await loop.run_in_executor(None, _sync)
                return (result or "").strip()
            except Exception as e:
                logger.exception("LLM generation failed: %s", e)
                # Если упало на нативной стороне — попробуем перезагрузить модель (однократно)
                # не блокируем текущий обработчик: запустим реинициализацию в фоне
                try:
                    asyncio.create_task(self._reinit_async())
                except Exception:
                    logger.exception("Cannot schedule reinit task.")
                return "Ошибка при генерации."
