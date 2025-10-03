# D:\telegram_reminder_bot\handlers\commands.py
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.chat_settings import chat_settings
from utils.memory import memory
from utils.notes import notes_store

router = Router()

def ai_picker_kbd() -> InlineKeyboardMarkup:
    kb = [[
        InlineKeyboardButton(text="🤖 Cerebras (Qwen)", callback_data="ai:cerebras"),
        InlineKeyboardButton(text="🧠 Gemini 2.5 Flash", callback_data="ai:gemini"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def note_kbd(note_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [   InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120") ],
    ])

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    current = chat_settings.get_ai(message.chat.id)
    await message.answer(
        "Выбери движок ИИ (можно менять):\n"
        f"Текущий: {current or 'не выбран'}\n\n"
        "Я помню контекст (SQLite, TTL=2ч). По умолчанию отвечаю коротко (≤500).\n"
        "Команда /notes — список заметок.",
        reply_markup=ai_picker_kbd()
    )

    # показать ожидающие/просроченные напоминания
    user_id = message.from_user.id
    chat_id = message.chat.id
    items = notes_store.list_pending(user_id, chat_id, limit=20)
    for it in items:
        await message.answer(
            f"📝 Заметка #{it['id']}:\n{it['text']}\n\nУже выполнено?",
            reply_markup=note_kbd(it["id"])
        )

@router.callback_query(F.data.startswith("ai:"))
async def on_ai_pick(cq: types.CallbackQuery):
    _, ai = cq.data.split(":", 1)
    chat_settings.set_ai(cq.message.chat.id, ai.lower().strip())
    memory.reset(cq.message.chat.id)  # очищаем контекст при переключении ИИ
    await cq.message.edit_text(
        f"✅ Движок установлен: {ai}\nℹ️ Контекст очищен. Можешь писать сообщения."
    )
    await cq.answer()

@router.message(Command("ai"))
async def cmd_ai(message: types.Message):
    await message.answer("Сменить движок ИИ:", reply_markup=ai_picker_kbd())

@router.message(Command("notes"))
async def cmd_notes(message: types.Message):
    # продублируем сюда для удобства
    user_id = message.from_user.id
    chat_id = message.chat.id
    items = notes_store.list_open_all(user_id, chat_id, limit=50)
    if not items:
        await message.answer("📝 Открытых заметок нет.")
        return
    await message.answer(f"📝 Ваши заметки ({len(items)}):")
    for it in items:
        await message.answer(f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{it['id']}"),
                InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{it['id']}"),
            ],
            [   InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{it['id']}:120") ],
        ]))

@router.message(Command("reset"))
async def cmd_reset(message: types.Message):
    memory.reset(message.chat.id)
    await message.answer("♻️ Контекст очищен.")
