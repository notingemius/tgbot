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

# === Настройки вебхука и окружения ===
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")  # например: https://notesbot.onrender.com
WEBHOOK_PATH   = os.getenv("WEBHOOK_PATH", "/webhook")      # путь, по которому Telegram шлёт апдейты
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")            # можно оставить пустым
DISABLE_BOT    = os.getenv("DISABLE_BOT", "0") == "1"       # быстрый "выключатель" бота
PORT           = int(os.getenv("PORT", "10000"))            # Render проставляет PORT

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set")

WEBHOOK_URL = f"{WEBHOOK_BASE}{WEBHOOK_PATH}" if WEBHOOK_BASE else None

# === Телеграм напоминалки (фон) ===
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
def note_kbd(note_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [   InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

async def reminder_loop(bot: Bot):
    while True:
        try:
            due = notes_store.list_due(limit=200)
            for it in due:
                # вернём заметку в open, чтобы напоминание не дублировалось
                notes_store.keep_open(it["id"])
                await bot.send_message(
                    it["chat_id"],
                    f"⏰ Напоминание по заметке #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                    reply_markup=note_kbd(it["id"])
                )
        except Exception:
            # не валим цикл из-за разовых ошибок
            pass
        await asyncio.sleep(60)

# === HTTP-хендлеры для Render (healthcheck, корень) ===
async def handle_root(request: web.Request):
    return web.Response(text="NotesBot webhook is running")

async def handle_health(request: web.Request):
    return web.Response(text="OK")

# === Хуки старта/остановки ===
async def on_startup(bot: Bot):
    if DISABLE_BOT:
        print("[startup] DISABLE_BOT=1 -> вебхук не устанавливаем, бот выключен")
        return
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_BASE не задан. Укажи https://<service>.onrender.com в переменной WEBHOOK_BASE")

    # Установка вебхука в Telegram (секрет пойдёт в заголовке X-Telegram-Bot-Api-Secret-Token)
    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    print(f"[startup] Webhook set to {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)
        print("[shutdown] Webhook deleted")

async def create_app():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(messages.router)

    # Aiohttp-приложение
    app = web.Application()
    app.add_routes([
        web.get("/", handle_root),
        web.get("/healthz", handle_health),
    ])

    # ✅ ВАЖНО: secret_token передаём в КОНСТРУКТОР, а НЕ в register()
    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET or None,  # <-- тут
    )
    handler.register(app, path=WEBHOOK_PATH)  # <-- без secret_token

    # Встраиваем жизненный цикл dp/bot в aiohttp
    setup_application(app, dp, bot=bot)

    # Наши хуки старта/остановки
    async def _startup(_app):
        await on_startup(bot)
        _app["reminder_task"] = asyncio.create_task(reminder_loop(bot))

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
