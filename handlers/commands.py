# handlers/commands.py
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from utils.chat_settings import chat_settings
from utils.notes import notes_store
from config import GEMINI_API_KEY, CEREBRAS_API_KEY

router = Router()

LANG_LABELS = {
    "menu_title": {"ru": "Главное меню", "uk": "Головне меню"},
    "menu_ai": {"ru": "🤖 ИИ", "uk": "🤖 ШІ"},
    "menu_notes": {"ru": "📝 Заметки", "uk": "📝 Нотатки"},
    "menu_daily": {"ru": "📅 Ежедневные", "uk": "📅 Щоденні"},
    "menu_lang": {"ru": "🌐 Язык", "uk": "🌐 Мова"},
    "pick_ai": {"ru": "Выбери движок ИИ:", "uk": "Обери двигун ШІ:"},
    "engine_set": {"ru": "✅ Движок установлен: ", "uk": "✅ Двигун встановлено: "},
    "ctx_cleared": {"ru": "ℹ️ Контекст очищен. Можешь писать сообщения.", "uk": "ℹ️ Контекст очищено. Можеш писати повідомлення."},
    "no_notes": {"ru": "Список заметок пуст. Пришли текст — добавлю.", "uk": "Список нотаток порожній. Надішли текст — додам."},
}
def t(lang: str, key: str) -> str:
    return LANG_LABELS.get(key, {}).get(lang, LANG_LABELS.get(key, {}).get("ru", key))

def main_menu_kbd(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "menu_ai"))],
            [KeyboardButton(text=t(lang, "menu_notes")), KeyboardButton(text=t(lang, "menu_daily"))],
            [KeyboardButton(text=t(lang, "menu_lang"))],
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
    # ПРИ ЛЮБОМ /start — показываем меню и ПОД ним клавиатуру выбора языка (как ты хотел)
    lang = chat_settings.get_lang(chat_id)  # вернёт 'ru' по умолчанию
    await message.answer(f"{t(lang,'menu_title')} ✅", reply_markup=main_menu_kbd(lang))
    await message.answer("Оберіть мову / Выберите язык", reply_markup=lang_kbd())

    # показать ожидающие заметки
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

# Меню — обрабатываем только тексты из него
MENU_TEXTS = {"🤖 ИИ","📝 Заметки","📅 Ежедневные","🤖 ШІ","📝 Нотатки","📅 Щоденні","🌐 Язык","🌐 Мова"}

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

    if text in {"🌐 Язык","🌐 Мова"}:
        await message.answer("Оберіть мову / Выберите язык", reply_markup=lang_kbd())
        return

# /debug — статус в чат
@router.message(Command("debug"))
async def cmd_debug(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    lang = chat_settings.get_lang(chat_id)
    ai = chat_settings.get_ai(chat_id) or "gemini"

    # считаем «ожидания ввода»
    from handlers.notes import _add_wait as notes_wait
    from handlers.daily import _add_wait as daily_wait

    notes_open = len(notes_store.list_open_all(user_id, chat_id, 999))
    try:
        from utils.daily import daily_store
        daily_count = len(daily_store.list(user_id, chat_id))
    except Exception:
        daily_count = -1

    text = (
        f"🧪 DEBUG\n"
        f"- lang: {lang}\n"
        f"- ai: {ai}\n"
        f"- GEMINI_API_KEY: {'set' if GEMINI_API_KEY else 'missing'}\n"
        f"- CEREBRAS_API_KEY: {'set' if CEREBRAS_API_KEY else 'missing'}\n"
        f"- notes open: {notes_open}\n"
        f"- daily count: {daily_count}\n"
        f"- waiting note text: {('yes' if (chat_id, user_id) in notes_wait else 'no')}\n"
        f"- waiting daily text: {('yes' if (chat_id, user_id) in daily_wait else 'no')}\n"
    )
    await message.answer(text)
