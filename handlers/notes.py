# handlers/notes.py
from aiogram import Router, types, F
from aiogram.filters import Command
from utils.notes import notes_store
from utils.chat_settings import chat_settings

# простейший «режим добавления заметки» (в памяти процесса)
_add_wait: set[tuple[int,int]] = set()   # {(chat_id, user_id)}

router = Router()

def note_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            types.InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [ types.InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

def add_top_kbd(lang: str) -> types.InlineKeyboardMarkup:
    txt = "➕ Добавить заметку" if lang=="ru" else "➕ Додати нотатку"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=txt, callback_data="note:add")]
    ])

async def open_notes_or_wait(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    lang = chat_settings.get_lang(chat_id)
    items = notes_store.list_open_all(user_id, chat_id, limit=50)
    if not items:
        _add_wait.add((chat_id, user_id))
        await message.answer("Список заметок пуст. Пришли текст — добавлю." if lang=="ru" else
                             "Список нотаток порожній. Надішли текст — я додам.")
        return
    await message.answer(f"📝 Ваши заметки ({len(items)}):" if lang=="ru" else f"📝 Ваші нотатки ({len(items)}):",
                         reply_markup=add_top_kbd(lang))
    for it in items:
        await message.answer(f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}", reply_markup=note_kbd(it["id"]))

@router.message(Command("notes"))
async def cmd_notes(message: types.Message):
    await open_notes_or_wait(message)

@router.callback_query(F.data == "note:add")
async def cb_note_add(cq: types.CallbackQuery):
    chat_id = cq.message.chat.id
    user_id = cq.from_user.id
    lang = chat_settings.get_lang(chat_id)
    _add_wait.add((chat_id, user_id))
    await cq.message.answer("Пришли текст заметки одной строкой." if lang=="ru" else
                            "Надішли текст нотатки одним рядком.")
    await cq.answer()

@router.message(F.text & ~F.text.startswith("/"))
async def catch_new_note(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if (chat_id, user_id) not in _add_wait:
        return  # не ждём, пускаем дальше другим хэндлерам
    text = (message.text or "").strip()
    if not text:
        return
    _add_wait.discard((chat_id, user_id))
    note_id = notes_store.add(user_id, chat_id, text)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="⏰ 1ч", callback_data=f"note:snooze:{note_id}:60"),
            types.InlineKeyboardButton(text="⏰ 2ч", callback_data=f"note:snooze:{note_id}:120"),
            types.InlineKeyboardButton(text="⏰ 3ч", callback_data=f"note:snooze:{note_id}:180"),
        ],
        [ types.InlineKeyboardButton(text="Без напоминания", callback_data=f"note:keep:{note_id}") ],
    ])
    await message.answer(f"📝 Заметка сохранена (#{note_id}):\n{text}", reply_markup=kb)

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
    await cq.message.delete()  # скрываем «живые» кнопки
    await cq.answer("Оставлено без напоминания")

@router.callback_query(F.data.startswith("note:snooze:"))
async def cb_note_snooze(cq: types.CallbackQuery):
    parts = cq.data.split(":")
    note_id = int(parts[2])
    minutes = int(parts[3]) if len(parts) > 3 else 120
    notes_store.snooze(note_id, minutes=minutes)
    await cq.message.edit_text(f"⏰ Напомню через {minutes} мин. (#{note_id})")
    await cq.answer("Напоминание установлено")
