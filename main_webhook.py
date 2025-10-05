# main_webhook.py
import os
import asyncio
import contextlib
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from aiogram.types.error_event import ErrorEvent
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    TELEGRAM_TOKEN, WEBHOOK_BASE, WEBHOOK_PATH, WEBHOOK_SECRET, CRON_SECRET,
    DISABLE_BOT, DISABLE_LOOP, PORT,
    GEMINI_API_KEY, CEREBRAS_API_KEY,
)
from handlers import commands, messages
from handlers import notes as notes_handlers
from handlers import daily as daily_handlers
from utils.notes import notes_store

# ======================= ЛОГИ =======================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("aiohttp.access").setLevel(logging.INFO)
log = logging.getLogger("app")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")

# fallback на переменную от Render
RENDER_EXTERNAL_URL = (os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")

def _pick_base_from_request(req: web.Request) -> str:
    # Пробуем заголовки прокси (Render)
    proto = req.headers.get("X-Forwarded-Proto") or req.scheme or "https"
    host  = req.headers.get("X-Forwarded-Host") or req.host
    if host:
        return f"{proto}://{host}"
    # последний шанс — SERVER_NAME
    return f"{proto}://{req.host}"

def _compose_url(base: str) -> str:
    return f"{base.rstrip('/')}{WEBHOOK_PATH}"

# =================== КНОПКИ ДЛЯ НОТИФАЕРА ===================
def note_kbd(note_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [InlineKeyboardButton(text="⏰ Отложить 2ч", callback_data=f"note:snooze:{note_id}:120")],
    ])

# =================== AIOHTTP MIDDLEWARE ===================
@web.middleware
async def access_logger(request: web.Request, handler):
    # Автоустановка вебхука "по пути"
    app = request.app
    is_webhook = (request.path == app["WEBHOOK_PATH"] and request.method == "POST")

    # если вебхук ещё не установлен и не запрещено — попробуем установить,
    # используя базу из запроса (scheme+host)
    if (not app["webhook_installed"]) and (not app["disable_bot"]) and request.method in ("GET", "HEAD"):
        base = app.get("webhook_base") or _pick_base_from_request(request)
        ok = await _ensure_webhook(app, base, drop=False)
        log.info("[auto-install] tried=%s ok=%s base=%s", True, ok, base)

    if is_webhook:
        secret_hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        xff = request.headers.get("X-Forwarded-For")
        log.info(
            "[webhook] <- POST %s from=%s len=%s secret_hdr=%s",
            request.path, xff or request.remote, request.content_length,
            "SET" if secret_hdr else "NONE"
        )
    try:
        resp = await handler(request)
        if is_webhook:
            log.info("[webhook] -> HTTP %s", getattr(resp, "status", "?"))
        return resp
    except Exception as e:
        log.exception("HTTP handler exception on %s %s: %s", request.method, request.path, e)
        raise

# =================== AIROGRAM MIDDLEWARE ===================
class UpdateLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            if isinstance(event, Message):
                log.info("[update.message] chat=%s user=%s text=%r",
                         event.chat.id, getattr(event.from_user, "id", None), event.text)
            elif isinstance(event, CallbackQuery):
                log.info("[update.callback] chat=%s user=%s data=%r",
                         getattr(event.message, "chat", None) and event.message.chat.id,
                         getattr(event.from_user, "id", None),
                         event.data)
            elif isinstance(event, Update):
                log.debug("[update.raw] %s", event.model_dump(exclude_none=True))
        except Exception:
            pass
        return await handler(event, data)

def install_error_logging(dp: Dispatcher):
    @dp.errors()
    async def on_error(event: ErrorEvent):
        try:
            upd = event.update.model_dump(exclude_none=True)
        except Exception:
            upd = "<cannot dump update>"
        log.exception("[aiogram] unhandled error. update=%s", upd, exc_info=event.exception)

# =================== УСТАНОВКА ВЕБХУКА ===================
async def _ensure_webhook(app: web.Application, base: str, drop: bool) -> bool:
    """Ставит вебхук, если base задан и вебхук ещё не установлен. Возвращает True при успехе."""
    if not base:
        return False
    bot: Bot = app["bot"]
    url = _compose_url(base)
    try:
        await bot.set_webhook(url=url, secret_token=app["webhook_secret"] or None, drop_pending_updates=drop)
        info = await bot.get_webhook_info()
        if info.url == url:
            app["webhook_installed"] = True
            app["webhook_base"] = base
            log.info("[webhook] installed url=%s", url)
            return True
        log.warning("[webhook] set_webhook did not stick. info.url=%s expected=%s", info.url, url)
        return False
    except Exception as e:
        log.exception("[webhook] set_webhook failed: %s", e)
        return False

# =================== HTTP ХЭНДЛЕРЫ ===================
async def handle_root(_: web.Request):
    return web.Response(text="NotesBot webhook is running")

async def handle_health(_: web.Request):
    return web.Response(text="OK")

async def handle_tginfo(request: web.Request):
    bot: Bot = request.app["bot"]
    me = await bot.get_me()
    info = await bot.get_webhook_info()
    return web.json_response({
        "me": {"id": me.id, "username": me.username, "name": me.first_name},
        "webhook": info.model_dump(),
        "expect_secret": bool(request.app["webhook_secret"]),
        "webhook_path": request.app["WEBHOOK_PATH"],
        "stored_base": request.app.get("webhook_base"),
        "installed": request.app["webhook_installed"],
        "render_external_url": RENDER_EXTERNAL_URL,
    })

async def handle_debug_config(_: web.Request):
    return web.json_response({
        "has_telegram_token": bool(TELEGRAM_TOKEN),
        "has_gemini_key": bool(GEMINI_API_KEY),
        "has_cerebras_key": bool(CEREBRAS_API_KEY),
        "webhook_base_env": WEBHOOK_BASE,
        "render_external_url": RENDER_EXTERNAL_URL,
        "webhook_path": WEBHOOK_PATH,
        "expect_secret": bool(WEBHOOK_SECRET),
    })

async def handle_install(request: web.Request):
    if request.app["disable_bot"]:
        return web.json_response({"ok": False, "reason": "DISABLE_BOT=1"}, status=400)
    # Пытаемся по приоритету: WEBHOOK_BASE -> RENDER_EXTERNAL_URL -> из запроса
    base = WEBHOOK_BASE or RENDER_EXTERNAL_URL or _pick_base_from_request(request)
    ok = await _ensure_webhook(request.app, base, drop=True)
    return web.json_response({"ok": ok, "base": base, "url": _compose_url(base)})

async def handle_test_send(request: web.Request):
    if CRON_SECRET and request.query.get("key") != CRON_SECRET:
        return web.Response(status=403, text="forbidden")
    chat_id = int(request.query.get("chat_id", "0") or "0")
    text = request.query.get("text", "test")
    if not chat_id:
        return web.Response(text="usage: /test/send?key=...&chat_id=<id>&text=hi")
    bot: Bot = request.app["bot"]
    try:
        await bot.send_message(chat_id, f"[test] {text}")
        return web.Response(text="ok")
    except Exception as e:
        log.exception("[test_send] failed: %s", e)
        return web.Response(status=500, text=f"error: {e}")

async def handle_cron_tick(request: web.Request):
    if CRON_SECRET and request.query.get("key") != CRON_SECRET:
        log.warning("[cron] forbidden: wrong or missing key")
        return web.Response(status=403, text="forbidden")
    bot: Bot = request.app["bot"]
    due = notes_store.list_due(limit=500)
    sent = 0
    for it in due:
        notes_store.keep_open(it["id"])
        try:
            await bot.send_message(
                it["chat_id"],
                f"⏰ Напоминание по заметке #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                reply_markup=note_kbd(it["id"])
            )
            sent += 1
        except Exception as e:
            log.exception("[cron] send_message failed chat=%s note=%s: %s", it["chat_id"], it["id"], e)
    log.info("[cron] sent=%d", sent)
    return web.Response(text=f"ok: sent={sent}")

# =================== REMINDER LOOP (опц.) ===================
async def reminder_loop(bot: Bot):
    while True:
        try:
            due = notes_store.list_due(limit=200)
            for it in due:
                notes_store.keep_open(it["id"])
                await bot.send_message(
                    it["chat_id"],
                    f"⏰ Напоминание по заметке #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                    reply_markup=note_kbd(it["id"])
                )
        except Exception as e:
            log.exception("[loop] error: %s", e)
        await asyncio.sleep(60)

# =================== STARTUP / SHUTDOWN ===================
async def on_startup(app: web.Application):
    bot: Bot = app["bot"]
    me = await bot.get_me()
    log.info("[startup] bot: @%s id=%s", me.username, me.id)
    log.info("[startup] BASE(env)=%s RENDER_EXTERNAL_URL=%s PATH=%s SECRET_SET=%s",
             WEBHOOK_BASE, RENDER_EXTERNAL_URL, app["WEBHOOK_PATH"], bool(app["webhook_secret"]))

    if app["disable_bot"]:
        log.warning("[startup] DISABLE_BOT=1 -> webhook NOT set")
        return

    # при старте пробуем WEBHOOK_BASE или RENDER_EXTERNAL_URL
    base = WEBHOOK_BASE or RENDER_EXTERNAL_URL
    if base:
        ok = await _ensure_webhook(app, base, drop=True)
        if not ok:
            log.warning("[startup] failed to install webhook from env, will retry lazily on first request")
    else:
        log.warning("[startup] no base URL yet; will try to auto-install on first external HTTP request")

async def on_shutdown(app: web.Application):
    bot: Bot = app["bot"]
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("[shutdown] webhook deleted")

# =================== APP FACTORY ===================
async def create_app():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    # логирование апдейтов и ошибок
    dp.message.middleware(UpdateLoggerMiddleware())
    dp.callback_query.middleware(UpdateLoggerMiddleware())
    install_error_logging(dp)

    # порядок: сначала узкие роутеры
    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(daily_handlers.router)
    dp.include_router(messages.router)

    app = web.Application(middlewares=[access_logger])
    app["bot"] = bot
    app["WEBHOOK_PATH"]   = WEBHOOK_PATH
    app["webhook_secret"] = WEBHOOK_SECRET or ""
    app["disable_bot"]    = bool(DISABLE_BOT)
    app["webhook_installed"] = False
    # предварительная база — если есть
    app["webhook_base"] = (WEBHOOK_BASE or RENDER_EXTERNAL_URL or "").rstrip("/")

    app.add_routes([
        web.get("/", handle_root),
        web.get("/healthz", handle_health),
        web.get("/tginfo", handle_tginfo),
        web.get("/debug/config", handle_debug_config),
        web.get("/install", handle_install),   # ручная установка вебхука
        web.get("/test/send", handle_test_send),
        web.get("/cron/tick", handle_cron_tick),
    ])

    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=(WEBHOOK_SECRET or None),  # если задан — запросы без секрета отвергнутся
    )
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    async def _startup(_app):
        await on_startup(_app)
        if not DISABLE_LOOP:
            _app["reminder_task"] = asyncio.create_task(reminder_loop(bot))
            log.info("[startup] reminder loop started")
        else:
            log.info("[startup] reminder loop DISABLED (use /cron/tick)")

    async def _cleanup(_app):
        task = _app.get("reminder_task")
        if task:
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        await on_shutdown(_app)

    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    return app

def main():
    app = asyncio.run(create_app())
    web.run_app(app, host="0.0.0.0", port=int(PORT))

if __name__ == "__main__":
    main()
