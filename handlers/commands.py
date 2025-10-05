# handlers/commands.py
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from utils.chat_settings import chat_settings
from utils.notes import notes_store

router = Router()

LANG_LABELS = {
    "choose": {"ru": "Выберите язык", "uk": "Оберіть мову"},
    "menu_title": {"ru": "Главное меню", "uk": "Головне меню"},
    "menu_ai": {"ru": "🤖 ИИ", "uk": "🤖 ШІ"},
    "menu_notes": {"ru": "📝 Заметки", "uk": "📝 Нотатки"},
    "menu_daily": {"ru": "📅 Ежедневные", "uk": "📅 Щоденні"},
    "pick_ai": {"ru": "Выбери движок ИИ:", "uk": "Обери двигун ШІ:"},
    "engine_set": {"ru": "✅ Движок установлен: ", "uk": "✅ Двигун встановлено: "},
    "ctx_cleared": {"ru": "ℹ️ Контекст очищен. Можешь писать сообщения.", "uk": "ℹ️ Контекст очищено. Можеш писати повідомлення."},
    "no_notes": {"ru": "Список заметок пуст. Пришли текст — добавлю.", "uk": "Список нотаток порожній. Надішли текст — додам."},
    "no_daily": {"ru": "Список ежедневных пуст. Отправь текст — добавлю.", "uk": "Список щоденних порожній. Надішли текст — додам."},
}
def t(lang: str, key: str) -> str:
    return LANG_LABELS.get(key, {}).get(lang, LANG_LABELS.get(key, {}).get("ru", key))

def main_menu_kbd(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "menu_ai"))],
            [KeyboardButton(text=t(lang, "menu_notes")), KeyboardButton(text=t(lang, "menu_daily"))],
        ],
        resize_keyboard=True, is_persistent=True
    )

def lang_kbd() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Українська", callback_data="lang:uk"),
        InlineKeyboardButton(text="Русский",   callback_data="lang:ru"),
    ]])

def ai_picker_kbd() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤖 Cerebras (Qwen)", callback_data="ai:cerebras"),
        InlineKeyboardButton(text="🧠 Gemini 2.5 Flash", callback_data="ai:gemini"),
    ]])

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    lang = chat_settings.get_lang(chat_id)
    # если язык ещё не установлен — попросим выбрать
    if lang not in ("ru", "uk"):
        await message.answer("Оберіть мову / Выберите язык", reply_markup=lang_kbd())
        return

    await message.answer(f"{t(lang,'menu_title')} ✅", reply_markup=main_menu_kbd(lang))

    # при заходе — показать открытые заметки (если есть)
    user_id = message.from_user.id
    items = notes_store.list_pending(user_id, chat_id, limit=20)
    if items:
        from .notes import note_kbd as _nk
        for it in items:
            await message.answer(
                f"📝 Заметка #{it['id']}:\n{it['text']}\n\nУже выполнено?",
                reply_markup=_nk(it["id"])
            )

@router.callback_query(F.data.startswith("lang:"))
async def on_lang(cq: types.CallbackQuery):
    lang = cq.data.split(":")[1]
    chat_settings.set_lang(cq.message.chat.id, lang)
    await cq.message.edit_text("✅")
    await cq.message.answer(t(lang, "menu_title") + " ✅", reply_markup=main_menu_kbd(lang))
    await cq.answer()

@router.message(Command("ai"))
async def cmd_ai(message: types.Message):
    lang = chat_settings.get_lang(message.chat.id)
    await message.answer(t(lang, "pick_ai"), reply_markup=ai_picker_kbd())

@router.callback_query(F.data.startswith("ai:"))
async def on_ai_pick(cq: types.CallbackQuery):
    _, ai = cq.data.split(":")
    chat_settings.set_ai(cq.message.chat.id, ai)
    from utils.memory import memory
    memory.reset(cq.message.chat.id)
    lang = chat_settings.get_lang(cq.message.chat.id)
    await cq.message.edit_text(t(lang, "engine_set") + ai + f"\n{t(lang,'ctx_cleared')}")
    await cq.answer()

# Обрабатываем только ТЕКСТЫ меню, чтобы не перехватывать все сообщения
MENU_TEXTS = {"🤖 ИИ","📝 Заметки","📅 Ежедневные","🤖 ШІ","📝 Нотатки","📅 Щоденні"}

@router.message(F.text.in_(MENU_TEXTS))
async def menu_router(message: types.Message):
    text = (message.text or "").strip()
    chat_id = message.chat.id
    user_id = message.from_user.id
    lang = chat_settings.get_lang(chat_id)

    if text in {"🤖 ИИ","🤖 ШІ"}:
        await message.answer(t(lang, "pick_ai"), reply_markup=ai_picker_kbd())
        return

    if text in {"📝 Заметки","📝 Нотатки"}:
        from .notes import open_notes_or_wait
        await open_notes_or_wait(message)
        return

    if text in {"📅 Ежедневные","📅 Щоденні"}:
        from .daily import show_daily_list
        await show_daily_list(message)
        return
