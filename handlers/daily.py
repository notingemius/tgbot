# D:\telegram_reminder_bot\handlers\daily.py
from aiogram import Router, types, F
from aiogram.filters import Command
from utils.daily import daily_store
from utils.chat_settings import chat_settings

router = Router()

def dkbd(task_id: int, lang: str) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Сделано сегодня" if lang=="ru" else "✅ Зроблено сьогодні",
                                       callback_data=f"daily:done:{task_id}"),
            types.InlineKeyboardButton(text="🗑 Удалить" if lang=="ru" else "🗑 Видалити",
                                       callback_data=f"daily:del:{task_id}"),
        ]
    ])

def top_add_kbd(lang: str) -> types.InlineKeyboardMarkup:
    txt = "➕ Добавить" if lang=="ru" else "➕ Додати"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=txt, callback_data="daily:add")]
    ])

@router.message(Command("daily"))
async def cmd_daily(message: types.Message):
    await show_daily_list(message)

async def show_daily_list(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    lang = chat_settings.get_lang(chat_id)
    tasks = daily_store.list(user_id, chat_id)
    if not tasks:
        await message.answer("Список ежедневных пуст. Отправь текст задачи, я добавлю." if lang=="ru" else
                             "Список щоденних порожній. Надішли текст завдання, я додам.")
        # пометим режим добавления через FSM-подобный флаг в память чата? Упростим: попросим просто прислать новое задание
        return
    await message.answer("📅 Ежедневные" if lang=="ru" else "📅 Щоденні", reply_markup=top_add_kbd(lang))
    for t in tasks:
        status = "✅ сегодня" if t["done_today"] else "⬜ сегодня"
        await message.answer(f"• #{t['id']}: {t['text']}  — {status}", reply_markup=dkbd(t["id"], lang))

@router.callback_query(F.data == "daily:add")
async def cb_daily_add(cq: types.CallbackQuery):
    lang = chat_settings.get_lang(cq.message.chat.id)
    await cq.message.answer("Пришли текст ежедневной активности одной строкой." if lang=="ru" else
                            "Надішли текст щоденної активності одним рядком.")
    await cq.answer()

@router.callback_query(F.data.startswith("daily:done:"))
async def cb_daily_done(cq: types.CallbackQuery):
    task_id = int(cq.data.split(":")[2])
    daily_store.mark_done(task_id)
    await cq.message.edit_text("✅ Отмечено на сегодня")
    await cq.answer("Готово")

@router.callback_query(F.data.startswith("daily:del:"))
async def cb_daily_del(cq: types.CallbackQuery):
    task_id = int(cq.data.split(":")[2])
    daily_store.delete(task_id)
    await cq.message.edit_text("🗑 Удалено")
    await cq.answer("Удалено")
