# handlers/messages.py
import re
import asyncio
from datetime import datetime
from aiogram import Router, types, F

from utils.memory import memory
from utils.chat_settings import chat_settings
from utils.notes import notes_store
from utils import info as info_api
from utils.gemini import ask_gemini

# Безопасный импорт Cerebras
try:
    from utils.llm import ask_cerebras as _ask_cerebras
    async def ask_cerebras(*a, **kw):
        return await _ask_cerebras(*a, **kw)
except Exception:
    async def ask_cerebras(*a, **kw):
        return "❗ Cerebras недоступен на сервере. Используй Gemini или установи 'cerebras-cloud-sdk'."

router = Router()

# ====== Триггеры инструментов ======
# Погода (терпимо к падежам/опечаткам)
WEATHER_RE = re.compile(
    r"(?:какая|какая сьогодні|какая сегодня|яка|яка сьогодні|погода|погодні|погоду|погоді|погоди)"
    r".{0,12}?(?:в|у)?\s*(?P<city>[\w\-\sА-Яа-яЁёІіЇїЄєҐґ]+)?", re.I)

# Праздники
HOLIDAY_RE = re.compile(r"(праздник|праздники|свято|свята)", re.I)

# Веб-поиск
SEARCH_RE  = re.compile(r"^(найди|поищи|поисчи|пошукай|знайди|загугли|google|пошук|поиск)\b[ :\-]*(?P<q>.+)$", re.I)

# «Какой сегодня день»
WHAT_DAY_RE = re.compile(r"(какой|який)\s+(сегодня|сьогодні)\s+(день|дата)", re.I)

# ====== Заметки — ТОЛЬКО по явному префиксу в начале строки ======
NOTE_PREFIX_RE = re.compile(
    r"^(?:!note|!n|заметка|запиши|запомни|пометь|поміть|напомни)\b[ :\-]+(?P<text>.+)$",
    re.I | re.S
)

def _day_string(lang: str) -> str:
    now = datetime.now()
    days_ru = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
    days_uk = ["понеділок","вівторок","середа","четвер","пʼятниця","субота","неділя"]
    day = days_uk[now.weekday()] if lang=="uk" else days_ru[now.weekday()]
    if lang=="uk":
        return f"Сьогодні {day}, {now.strftime('%d.%m.%Y')}."
    return f"Сегодня {day}, {now.strftime('%d.%m.%Y')}."

@router.message(F.text & ~F.text.startswith("/"))
async def any_text(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or ""
    lang = chat_settings.get_lang(chat_id)

    # A) День/дата — считаем локально
    if WHAT_DAY_RE.search(text):
        await message.answer(_day_string(lang))
        return

    # B) Погода
    wm = WEATHER_RE.search(text)
    if wm:
        raw_city = (wm.group("city") or "").strip()
        # убрать дату из типа "Києві 05.10.2025"
        city = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", "", raw_city).strip()
        if not city:
            city = "Київ" if lang=="uk" else "Киев"
        try:
            ans = await info_api.weather_today(city, lang)
        except Exception as e:
            ans = f"⚠️ Ошибка погоды: {e}"
        await message.answer(ans)
        return

    # C) Праздники
    if HOLIDAY_RE.search(text):
        country = "UA" if lang=="uk" else "RU"
        try:
            hs = await info_api.holidays_today(country)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка праздников: {e}")
            return
        if not hs:
            await message.answer("Сьогодні офіційних свят немає." if lang=="uk" else "Сегодня официальных праздников нет.")
        else:
            lines = [f"• {h.get('localName') or h.get('name')}" for h in hs]
            await message.answer(("Свята сьогодні:\n" if lang=="uk" else "Праздники сегодня:\n") + "\n".join(lines))
        return

    # D) Веб-поиск
    sm = SEARCH_RE.search(text)
    if sm:
        query = (sm.group("q") or "").strip()
        try:
            ans = await info_api.web_search(query, lang, limit=3)
        except Exception as e:
            ans = f"⚠️ Помилка пошуку: {e}" if lang=="uk" else f"⚠️ Ошибка поиска: {e}"
        await message.answer(ans)
        return

    # E) Заметка — ТОЛЬКО ЯВНЫЙ ПРЕФИКС
    m = NOTE_PREFIX_RE.search(text)
    if m:
        note_text = (m.group("text") or "").strip()
        if note_text:
            note_id = notes_store.add(user_id=user_id, chat_id=chat_id, text=note_text)
            await message.answer(f"📝 Заметка сохранена (#{note_id}):\n{note_text}")
            return

    # F) ИИ-диалог (с таймаутом, движок из настроек чата)
    engine = (chat_settings.get_ai(chat_id) or "gemini").strip().lower()
    memory.add(chat_id, "user", text)
    allow_long = bool(re.search(r'подроб|разверну|много', text, flags=re.I))
    history = memory.get(chat_id)

    try:
        if engine == "gemini":
            reply = await asyncio.wait_for(
                ask_gemini(history=history, allow_long=allow_long, max_len=600),
                timeout=25
            )
        else:
            reply = await asyncio.wait_for(
                ask_cerebras(history=history, allow_long=allow_long, max_len=600),
                timeout=25
            )
    except asyncio.TimeoutError:
        reply = "⚠️ Превышено время ответа ИИ (25с). Попробуй ещё раз или переключи модель."
    except Exception as e:
        reply = f"⚠️ Ошибка ИИ: {e}"

    memory.add(chat_id, "assistant", reply)
    await message.answer(reply)
