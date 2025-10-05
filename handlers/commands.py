# D:\telegram_reminder_bot\handlers\commands.py
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from utils.chat_settings import chat_settings
from utils.memory import memory
from utils.notes import notes_store

router = Router()

LANG_LABELS = {
    "choose": {"ru": "Выберите язык", "uk": "Оберіть мову"},
    "lang_ru": {"ru": "Русский", "uk": "Російська"},
    "lang_uk": {"ru": "Українська", "uk": "Українська"},
    "menu_title": {"ru": "Главное меню", "uk": "Головне меню"},
    "menu_ai": {"ru": "🤖 ИИ", "uk": "🤖 ШІ"},
    "menu_notes": {"ru": "📝 Заметки", "uk": "📝 Нотатки"},
    "menu_daily": {"ru": "📅 Ежедневные", "uk": "📅 Щоденні"},
    "engine_set": {"ru": "✅ Движок установлен: ", "uk": "✅ Двигун встановлено: "},
    "ctx_cleared": {"ru": "ℹ️ Контекст очищен. Можешь писать сообщения.", "uk": "ℹ️ Контекст очищено. Можеш писати повідомлення."},
    "pick_ai": {"ru": "Выбери движок ИИ:", "uk": "Обери двигун ШІ:"},
    "no_open_notes": {"ru": "📝 Открытых заметок нет.", "uk": "📝 Відкритих нотаток немає."},
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

def lang_kbd() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Українська")],[KeyboardButton(text="Русский")]],
        resize_keyboard=True, one_time_keyboard=True
    )

def ai_picker_kbd() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤖 Cerebras (Qwen)", callback_data="ai:cerebras"),
        InlineKeyboardButton(text="🧠 Gemini 2.5 Flash", callback_data="ai:gemini"),
    ]])

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    lang = chat_settings.get_lang(chat_id)
    if lang not in ("ru", "uk"):
        await message.answer("Оберіть мову / Выберите язык", reply_markup=lang_kbd())
        return
    await message.answer(f"{t(lang,'menu_title')} ✅", reply_markup=main_menu_kbd(lang))

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

@router.message(F.text.in_({"Русский","Українська"}))
async def on_lang_pick(message: types.Message):
    val = message.text.strip()
    lang = "uk" if val.lower().startswith("укр") else "ru"
    chat_settings.set_lang(message.chat.id, lang)
    await message.answer(t(lang, "menu_title") + " ✅", reply_markup=main_menu_kbd(lang))

@router.message(Command("ai"))
async def cmd_ai(message: types.Message):
    lang = chat_settings.get_lang(message.chat.id)
    await message.answer(t(lang, "pick_ai"), reply_markup=ai_picker_kbd())

@router.callback_query(F.data.startswith("ai:"))
async def on_ai_pick(cq: types.CallbackQuery):
    _, ai = cq.data.split(":", 1)
    chat_settings.set_ai(cq.message.chat.id, ai.lower().strip())
    memory.reset(cq.message.chat.id)
    lang = chat_settings.get_lang(cq.message.chat.id)
    await cq.message.edit_text(t(lang, "engine_set") + ai + f"\n{t(lang,'ctx_cleared')}")
    await cq.answer()

# ⬇️ ВАЖНО: этот хэндлер реагирует ТОЛЬКО на тексты меню,
# чтобы не перехватывать все сообщения и не глушить ИИ/заметки.
MENU_TEXTS = {"🤖 ИИ","📝 Заметки","📅 Ежедневные","🤖 ШІ","📝 Нотатки","📅 Щоденні"}
@router.message(F.text.in_(MENU_TEXTS))
async def menu_router(message: types.Message):
    text = (message.text or "").strip()
    lang = chat_settings.get_lang(message.chat.id)

    if text in {t(lang,"menu_ai"), "🤖 ИИ","🤖 ШІ"}:
        await message.answer(t(lang, "pick_ai"), reply_markup=ai_picker_kbd())
        return

    if text in {t(lang,"menu_notes"), "📝 Заметки","📝 Нотатки"}:
        user_id = message.from_user.id
        chat_id = message.chat.id
        items = notes_store.list_open_all(user_id, chat_id, limit=50)
        from .notes import note_kbd, add_top_kbd, set_create_wait
        if not items:
            set_create_wait(chat_id, user_id)
            await message.answer("Список пуст. Пришли текст заметки — добавлю." if lang=="ru"
                                 else "Список порожній. Надішли текст нотатки — додам.")
            return
        await message.answer(f"📝 Ваши заметки ({len(items)}):" if lang=="ru" else f"📝 Ваші нотатки ({len(items)}):",
                             reply_markup=add_top_kbd(lang))
        for it in items:
            await message.answer(f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}", reply_markup=note_kbd(it["id"]))
        return

    if text in {t(lang,"menu_daily"), "📅 Ежедневные","📅 Щоденні"}:
        from .daily import show_daily_list, set_daily_wait
        # show_daily_list сам покажет список; если пуст — включит "ожидание ввода"
        await show_daily_list(message)
        return
