# D:\telegram_reminder_bot\main_webhook.py
import os
import asyncio
import contextlib

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import TELEGRAM_TOKEN
from handlers import commands, messages
from handlers import notes as notes_handlers
from handlers import daily as daily_handlers
from utils.notes import notes_store

WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_PATH   = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CRON_SECRET    = os.getenv("CRON_SECRET", "")
DISABLE_BOT    = os.getenv("DISABLE_BOT", "0") == "1"
DISABLE_LOOP   = os.getenv("DISABLE_LOOP", "1") == "1"  # по умолчанию используем /cron/tick на free
PORT           = int(os.getenv("PORT", "10000"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")

WEBHOOK_URL = f"{WEBHOOK_BASE}{WEBHOOK_PATH}" if WEBHOOK_BASE else None

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
def note_kbd(note_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [InlineKeyboardButton(text="⏰ Отложить 2ч", callback_data=f"note:snooze:{note_id}:120")],
    ])

# ---------- HTTP handlers ----------
async def handle_root(request: web.Request):
    return web.Response(text="NotesBot webhook is running")

async def handle_health(request: web.Request):
    return web.Response(text="OK")

async def handle_cron_tick(request: web.Request):
    if CRON_SECRET and request.query.get("key") != CRON_SECRET:
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
        except Exception:
            pass
    return web.Response(text=f"ok: sent={sent}")

async def handle_tginfo(request: web.Request):
    """Диагностика: кто я, какой вебхук стоит у Telegram, и были ли ошибки доставки."""
    bot: Bot = request.app["bot"]
    me = await bot.get_me()
    info = await bot.get_webhook_info()
    # pydantic v2 -> model_dump()
    payload = {
        "me": {"id": me.id, "username": me.username, "name": me.first_name},
        "webhook": info.model_dump(),
    }
    return web.json_response(payload)

# ---------- reminder loop (опц.) ----------
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
        except Exception:
            pass
        await asyncio.sleep(60)

# ---------- startup / shutdown ----------
async def on_startup(bot: Bot):
    me = await bot.get_me()
    print(f"[startup] bot: @{me.username} (id={me.id})")
    if DISABLE_BOT:
        print("[startup] DISABLE_BOT=1 -> webhook не ставим")
        return
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_BASE не задан (пример: https://<service>.onrender.com)")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    print(f"[startup] webhook set to {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)
        print("[shutdown] webhook deleted")

# ---------- app factory ----------
async def create_app():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(daily_handlers.router)
    dp.include_router(messages.router)

    app = web.Application()
    app["bot"] = bot
    app.add_routes([
        web.get("/", handle_root),
        web.get("/healthz", handle_health),
        web.get("/cron/tick", handle_cron_tick),
        web.get("/tginfo", handle_tginfo),  # <-- новая диагностика
    ])

    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET or None,
    )
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    async def _startup(_app):
        await on_startup(bot)
        if not DISABLE_LOOP:
            _app["reminder_task"] = asyncio.create_task(reminder_loop(bot))
            print("[startup] reminder loop started")
        else:
            print("[startup] reminder loop DISABLED (use /cron/tick)")

    async def _cleanup(_app):
        task = _app.get("reminder_task")
        if task:
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        await on_shutdown(bot)

    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    return app

def main():
    app = asyncio.run(create_app())
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
