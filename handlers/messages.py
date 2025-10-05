# handlers/messages.py
import re
from aiogram import Router, types, F
from utils.memory import memory
from utils.chat_settings import chat_settings
from utils.notes import notes_store
from utils import info as info_api
from utils.gemini import ask_gemini
from utils.llm import ask_cerebras

router = Router()

NOTE_TRIGGERS = r"(заметка|запомни|запиши|пометь|поміть|напомни|todo|to-?do|сделать|сделай)"
WEATHER_RE = re.compile(r"(погода|погоду|погоді|погоди)(?:\s+в| у)?\s*(?P<city>[\w\-\sА-Яа-яЁёІіЇїЄєҐґ]+)?", re.I)
HOLIDAY_RE = re.compile(r"(праздник|праздники|свято|свята)", re.I)

def _extract_note(text: str) -> str | None:
    if not text:
        return None
    m = re.search(rf"{NOTE_TRIGGERS}\b[:\- ]*(.+)$", text, flags=re.I | re.S)
    if m:
        return m.group(2).strip()
    if re.search(rf"{NOTE_TRIGGERS}\b", text, flags=re.I):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return lines[-1]
    return None

@router.message(F.text & ~F.text.startswith("/"))
async def any_text(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or ""
    lang = chat_settings.get_lang(chat_id)

    # B) Быстрые инструменты: погода / праздники
    wm = WEATHER_RE.search(text)
    if wm:
        city = (wm.group("city") or "").strip() or ("Київ" if lang=="uk" else "Киев")
        try:
            ans = await info_api.weather_today(city, lang)
        except Exception as e:
            ans = f"⚠️ Ошибка погоды: {e}"
        await message.answer(ans)
        return

    if HOLIDAY_RE.search(text):
        country = "UA" if lang=="uk" else "RU"
        try:
            hs = await info_api.holidays_today(country)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка праздников: {e}")
            return
        if not hs:
            await message.answer("Сегодня официальных праздников нет." if lang=="ru" else "Сьогодні офіційних свят немає.")
        else:
            lines = [f"• {h.get('localName') or h.get('name')}" for h in hs]
            await message.answer(("Праздники сегодня:\n" if lang=="ru" else "Свята сьогодні:\n") + "\n".join(lines))
        return

    # C) Заметка по триггеру
    note_text = _extract_note(text)
    if note_text:
        note_id = notes_store.add(user_id=user_id, chat_id=chat_id, text=note_text)
        await message.answer(f"📝 Заметка сохранена (#{note_id}):\n{note_text}")
        return

    # D) ИИ-диалог
    engine = (chat_settings.get_ai(chat_id) or "gemini").strip().lower()
    memory.add(chat_id, "user", text)
    allow_long = bool(re.search(r'подроб|разверну|много', text, flags=re.I))
    history = memory.get(chat_id)

    try:
        if engine == "gemini":
            reply = await ask_gemini(history=history, allow_long=allow_long, max_len=600)
        else:
            reply = await ask_cerebras(history=history, allow_long=allow_long, max_len=600)
    except Exception as e:
        reply = f"⚠️ Ошибка ИИ: {e}"

    memory.add(chat_id, "assistant", reply)
    await message.answer(reply)
