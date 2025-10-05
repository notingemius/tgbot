# D:\telegram_reminder_bot\handlers\notes.py
from aiogram import Router, types, F
from aiogram.filters import Command
from utils.notes import notes_store
from utils.chat_settings import chat_settings
from utils.note_runtime import set_create_wait, is_create_wait, pop_create_wait

router = Router()

def note_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            types.InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [ types.InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

def remind_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="⏰ 1ч", callback_data=f"note:snooze:{note_id}:60"),
            types.InlineKeyboardButton(text="⏰ 2ч", callback_data=f"note:snooze:{note_id}:120"),
            types.InlineKeyboardButton(text="⏰ 3ч", callback_data=f"note:snooze:{note_id}:180"),
        ],
        [ types.InlineKeyboardButton(text="Без напоминания", callback_data=f"note:keep:{note_id}") ],
    ])

def add_top_kbd(lang: str) -> types.InlineKeyboardMarkup:
    txt = "➕ Добавить заметку" if lang=="ru" else "➕ Додати нотатку"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=txt, callback_data="note:add")]
    ])

# экспортируем для commands.menu_router
add_top_kbd.__all__ = ["add_top_kbd", "note_kbd", "set_create_wait"]

@router.message(Command("notes"))
async def cmd_notes(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    lang = chat_settings.get_lang(chat_id)
    items = notes_store.list_open_all(user_id, chat_id, limit=50)
    if not items:
        set_create_wait(chat_id, user_id)
        await message.answer("📝 Открытых заметок нет.\nПришли текст — добавлю.")
        return
    await message.answer(f"📝 Ваши заметки ({len(items)}):", reply_markup=add_top_kbd(lang))
    for it in items:
        txt = f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}"
        await message.answer(txt, reply_markup=note_kbd(it["id"]))

@router.callback_query(F.data == "note:add")
async def cb_note_add(cq: types.CallbackQuery):
    lang = chat_settings.get_lang(cq.message.chat.id)
    set_create_wait(cq.message.chat.id, cq.from_user.id)
    await cq.message.answer("Пришли текст заметки одной строкой." if lang=="ru" else
                            "Надішли текст нотатки одним рядком.")
    await cq.answer()

# перехватываем текст, если ждём ввод новой заметки
@router.message(F.text & ~F.text.startswith("/"))
async def catch_new_note(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not is_create_wait(chat_id, user_id):
        return  # не ждём — пусть обрабатывают другие роутеры
    text = (message.text or "").strip()
    if not text:
        return
    pop_create_wait(chat_id, user_id)
    note_id = notes_store.add(user_id, chat_id, text)
    await message.answer(f"📝 Заметка сохранена (#{note_id}):\n{text}", reply_markup=remind_kbd(note_id))

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
    await cq.message.delete()  # удалить сообщение с кнопками
    await cq.answer("Оставлено без напоминания")

@router.callback_query(F.data.startswith("note:snooze:"))
async def cb_note_snooze(cq: types.CallbackQuery):
    parts = cq.data.split(":")
    note_id = int(parts[2])
    minutes = int(parts[3]) if len(parts) > 3 else 120
    notes_store.snooze(note_id, minutes=minutes)
    await cq.message.edit_text(f"⏰ Напомню через {minutes} мин. (#{note_id})")
    await cq.answer("Напоминание установлено")
