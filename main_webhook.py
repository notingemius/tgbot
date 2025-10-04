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
from utils.notes import notes_store

WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")  # https://<your>.onrender.com
WEBHOOK_PATH   = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CRON_SECRET    = os.getenv("CRON_SECRET", "")               # секрет для /cron/tick
DISABLE_BOT    = os.getenv("DISABLE_BOT", "0") == "1"
DISABLE_LOOP   = os.getenv("DISABLE_LOOP", "1") == "1"      # по умолчанию отключаем фон.цикл на free
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
        [   InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

async def handle_root(request: web.Request):
    return web.Response(text="NotesBot webhook is running")

async def handle_health(request: web.Request):
    return web.Response(text="OK")

async def handle_cron_tick(request: web.Request):
    # защита по секрету
    if CRON_SECRET:
        if request.query.get("key") != CRON_SECRET:
            return web.Response(status=403, text="forbidden")
    bot: Bot = request.app["bot"]
    due = notes_store.list_due(limit=500)
    sent = 0
    for it in due:
        notes_store.keep_open(it["id"])  # возвращаем в open, чтобы не дублировалось
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

async def on_startup(bot: Bot):
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

async def create_app():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(messages.router)

    app = web.Application()
    app["bot"] = bot
    app.add_routes([
        web.get("/", handle_root),
        web.get("/healthz", handle_health),
        web.get("/cron/tick", handle_cron_tick),  # внешний пинг вызывает напоминания
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
            print("[startup] reminder loop DISABLED (use /cron/tick from external pinger)")

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
