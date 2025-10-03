# D:\telegram_reminder_bot\handlers\messages.py
import re
from aiogram import Router, types, F
from utils.llm import ask_ai as ask_cerebras
from utils.gemini import ask_gemini
from utils.memory import memory
from utils.chat_settings import chat_settings
from utils.notes import notes_store
from utils.note_runtime import get_pending, pop_pending

router = Router()

NOTE_TRIGGERS = r"(заметка|запомни|запиши|пометь|поміть|напомни|todo|to-?do|сделать|сделай)"

def _extract_note(text: str) -> str | None:
    if not text:
        return None
    # 1) Если после триггера есть текст — берём его
    m = re.search(rf"{NOTE_TRIGGERS}\b[:\- ]*(.+)$", text, flags=re.I | re.S)
    if m:
        body = m.group(2).strip()
        return body
    # 2) Если триггер есть, но на новой строке — берём последнюю непустую строку
    if re.search(rf"{NOTE_TRIGGERS}\b", text, flags=re.I):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return lines[-1]
    return None

def _parse_duration_to_minutes(s: str) -> int | None:
    s = (s or "").strip().lower().replace(" ", "")
    if not s:
        return None
    # 1.5ч
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)ч", s)
    if m:
        hours = float(m.group(1).replace(",", "."))
        return max(1, int(hours * 60))
    # 90м / 90мин
    m = re.fullmatch(r"(\d+)м(ин)?", s)
    if m:
        return max(1, int(m.group(1)))
    # 2h / 120min
    m = re.fullmatch(r"(\d+)h", s)
    if m:
        return max(1, int(m.group(1)) * 60)
    m = re.fullmatch(r"(\d+)(min|mins|minute|minutes)", s)
    if m:
        return max(1, int(m.group(1)))
    # просто число — считаем часами
    m = re.fullmatch(r"(\d+)", s)
    if m:
        return max(1, int(m.group(1)) * 60)
    return None

def _remind_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="⏰ 1ч", callback_data=f"note:snooze:{note_id}:60"),
            types.InlineKeyboardButton(text="⏰ 2ч", callback_data=f"note:snooze:{note_id}:120"),
            types.InlineKeyboardButton(text="⏰ 3ч", callback_data=f"note:snooze:{note_id}:180"),
        ],
        [
            types.InlineKeyboardButton(text="Без напоминания", callback_data=f"note:keep:{note_id}"),
            types.InlineKeyboardButton(text="Ввести…",         callback_data=f"note:custom:{note_id}"),
        ],
    ])

def _note_kbd(note_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да (выполнено)", callback_data=f"note:done:{note_id}"),
            types.InlineKeyboardButton(text="❌ Нет",            callback_data=f"note:keep:{note_id}"),
        ],
        [
            types.InlineKeyboardButton(text="⏰ Отложить 2ч",    callback_data=f"note:snooze:{note_id}:120"),
        ],
    ])

@router.message(F.text & ~F.text.startswith("/"))
async def any_text(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or ""

    # A) Ожидание кастомного интервала напоминания
    pending_note_id = get_pending(chat_id, user_id)
    if pending_note_id:
        minutes = _parse_duration_to_minutes(text)
        if minutes is None:
            await message.answer("Не понял интервал. Примеры: `2ч`, `90м`, `1.5ч`.", parse_mode="Markdown")
            return
        pop_pending(chat_id, user_id)
        notes_store.snooze(pending_note_id, minutes=minutes)
        await message.answer(f"⏰ Напомню через {minutes} мин. (#{pending_note_id})")
        return

    # B) Команда «заметки» словом
    if text.strip().lower() in {"заметки", "заметка", "notes"}:
        items = notes_store.list_open_all(user_id, chat_id, limit=50)
        if not items:
            await message.answer("📝 Открытых заметок нет.")
            return
        await message.answer(f"📝 Ваши заметки ({len(items)}):")
        for it in items:
            await message.answer(f"• #{it['id']}: {it['text']}\nСтатус: {it['status']}", reply_markup=_note_kbd(it["id"]))
        return

    # C) Распознавание заметки в свободном тексте (не требуем начала строки)
    note_text = _extract_note(text)
    if note_text:
        note_id = notes_store.add(user_id=user_id, chat_id=chat_id, text=note_text)
        await message.answer(
            f"📝 Заметка сохранена (#{note_id}):\n{note_text}\n\nКогда напомнить?",
            reply_markup=_remind_kbd(note_id)
        )
        return

    # D) Обычный ИИ-диалог
    engine = (chat_settings.get_ai(chat_id) or "").strip().lower()
    if engine not in ("gemini", "cerebras"):
        await message.answer("Сначала выбери ИИ через /ai.")
        return

    memory.add(chat_id, "user", text)
    allow_long = bool(re.search(r'подроб|разверну|много', text, flags=re.I))
    history = memory.get(chat_id)

    if engine == "gemini":
        reply = await ask_gemini(history=history, allow_long=allow_long, max_len=500)
    else:
        reply = await ask_cerebras(history=history, allow_long=allow_long, max_len=500)

    memory.add(chat_id, "assistant", reply)
    await message.answer(reply)
