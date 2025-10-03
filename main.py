# D:\telegram_reminder_bot\main.py
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiohttp import web

from config import TELEGRAM_TOKEN
from handlers import commands, messages
from handlers import notes as notes_handlers
from utils.notes import notes_store

# --- HTTP: минимальный сервер для Render (healthcheck) ---
async def handle_root(request: web.Request):
    return web.Response(text="NotesBot is running")

async def handle_health(request: web.Request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.add_routes([
        web.get("/", handle_root),
        web.get("/healthz", handle_health),
    ])
    port = int(os.getenv("PORT", "10000"))  # Render проставляет PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    # держим сервер живым
    await asyncio.Event().wait()

# --- Телеграм напоминалки ---
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
                notes_store.keep_open(it["id"])  # вернём в open, чтобы не дублировалось
                await bot.send_message(
                    it["chat_id"],
                    f"⏰ Напоминание по заметке #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                    reply_markup=note_kbd(it["id"])
                )
        except Exception:
            # не валим цикл из-за разовых ошибок
            pass
        await asyncio.sleep(60)

# --- Точка входа ---
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    # подключаем роутеры
    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(messages.router)

    # поднимаем HTTP-сервер (для Render) и напоминатель
    http_task = asyncio.create_task(start_http_server())
    remind_task = asyncio.create_task(reminder_loop(bot))

    try:
        # запускаем long-polling
        await dp.start_polling(bot)
    finally:
        # аккуратно завершим фоновые задачки
        for t in (http_task, remind_task):
            t.cancel()
            with contextlib.suppress(Exception):
                await t

if __name__ == "__main__":
    import contextlib
    asyncio.run(main())
