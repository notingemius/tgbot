# D:\telegram_reminder_bot\main.py
import asyncio
from aiogram import Bot, Dispatcher
from config import TELEGRAM_TOKEN
from handlers import commands, messages
from handlers import notes as notes_handlers
from utils.notes import notes_store

# вспомогательная клавиатура сюда, чтобы не было циклических импортов
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
    # простой планировщик: проверяем раз в 60 сек просроченные snooze
    while True:
        try:
            due = notes_store.list_due(limit=200)
            for it in due:
                # переведём заметку обратно в open, чтобы не дублировалась
                notes_store.keep_open(it["id"])
                await bot.send_message(
                    it["chat_id"],
                    f"⏰ Напоминание по заметке #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                    reply_markup=note_kbd(it["id"])
                )
        except Exception:
            # глушим любые ошибки, чтобы цикл не умирал
            pass
        await asyncio.sleep(60)

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(messages.router)

    # запускаем фоновый напоминатель
    asyncio.create_task(reminder_loop(bot))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
