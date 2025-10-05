# D:\telegram_reminder_bot\handlers\notes.py
from aiogram import Router, types, F
from aiogram.filters import Command
from utils.notes import notes_store

router = Router()

def note_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            types.InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [ types.InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

@router.message(Command("notes"))
async def cmd_notes(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    items = notes_store.list_open_all(user_id, chat_id, limit=50)
    if not items:
        await message.answer("📝 Открытых заметок нет.")
        return
    await message.answer(f"📝 Ваши заметки ({len(items)}):")
    for it in items:
        txt = f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}"
        await message.answer(txt, reply_markup=note_kbd(it["id"]))

@router.callback_query(F.data.startswith("note:done:"))
async def cb_note_done(cq: types.CallbackQuery):
    note_id = int(cq.data.split(":")[2])
    notes_store.set_done(note_id)
    await cq.message.edit_text(f"✅ Выполнено! (#{note_id})")
    await cq.answer("Отмечено как выполнено")

@router.callback_query(F.data.startswith("note:keep:"))
async def cb_note_keep(cq: types.CallbackQuery):
    note_id = int(cq.data.split(":")[2])
    notes_store.keep_open(note_id)
    # 👉 удаляем сообщение, чтобы «активные кнопки» не висели
    await cq.message.delete()
    await cq.answer("Оставлено без напоминания")

@router.callback_query(F.data.startswith("note:snooze:"))
async def cb_note_snooze(cq: types.CallbackQuery):
    parts = cq.data.split(":")
    note_id = int(parts[2])
    minutes = int(parts[3]) if len(parts) > 3 else 120
    notes_store.snooze(note_id, minutes=minutes)
    await cq.message.edit_text(f"⏰ Напомню через {minutes} мин. (#{note_id})")
    await cq.answer("Напоминание установлено")
