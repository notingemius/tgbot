# utils/info.py
import asyncio
import aiohttp
import re
import html
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

# ---- нормализация городов и простые алиасы (опечатки/падежи) ----
_CITY_ALIASES = {
    # Kyiv
    "киев": "Київ",
    "києв": "Київ",
    "киеве": "Київ",
    "киеву": "Київ",
    "києві": "Київ",
    "києву": "Київ",
    "kyiv": "Київ",
    "kiev": "Київ",
    "киев-город": "Київ",
    # add here other частые города при желании
}

_WS = r"[ \t\u00A0]+"

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[.,!?;:()\"'«»]+", " ", s)
    s = re.sub(_WS, " ", s).strip()
    s = s.replace("ё", "е")
    return s

def _cleanup_city(raw: str) -> str:
    s = _norm(raw)
    # убираем предлоги/хвосты: "в/у/в городе/місті ..."
    s = re.sub(rf"^(в городе|в місті|в|у)\s+", "", s)
    # убираем явные даты
    s = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", "", s).strip()
    # алиасы
    if s in _CITY_ALIASES:
        return _CITY_ALIASES[s]
    # иногда пишут "києв" -> нормализуем окончание
    s = re.sub(r"(и|і|у|е|ю|я|й)$", "", s)  # очень мягко обрезаем падежный хвост
    return s.capitalize()

# ---------- HTTP ----------
_TIMEOUT = aiohttp.ClientTimeout(total=10)

async def _fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url, timeout=_TIMEOUT) as r:
        r.raise_for_status()
        return await r.json()

async def _fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=_TIMEOUT) as r:
        r.raise_for_status()
        return await r.text()

# ---------- Погода ----------
async def _geocode_city(session: aiohttp.ClientSession, city: str, lang: str) -> Optional[Dict[str, Any]]:
    q = _cleanup_city(city)
    if not q:
        return None
    url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={quote(q)}&count=1&language={'uk' if lang=='uk' else 'ru'}&format=json"
    )
    data = await _fetch_json(session, url)
    res = (data or {}).get("results") or []
    return res[0] if res else None

async def weather_today(city: str, lang: str = "ru") -> str:
    """Вернёт краткий отчёт о погоде сегодня."""
    city = (city or "").strip()
    if not city:
        city = "Київ" if lang == "uk" else "Киев"

    async with aiohttp.ClientSession() as session:
        geo = await _geocode_city(session, city, lang)
        if not geo:
            return ("Місто не знайдено. " if lang == "uk" else "Город не найден. ") + _cleanup_city(city)

        lat, lon = float(geo["latitude"]), float(geo["longitude"])
        show_name = geo.get("name") or city

        # текущие + дневной прогноз
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,wind_speed_10m,relative_humidity_2m"
            "&hourly=temperature_2m,precipitation_probability"
            "&forecast_days=1&timezone=auto"
        )
        try:
            data = await _fetch_json(session, url)
        except Exception as e:
            return ("Помилка погоди: " if lang == "uk" else "Ошибка погоды: ") + str(e)

    cur = (data or {}).get("current") or {}
    hourly = (data or {}).get("hourly") or {}
    temps = hourly.get("temperature_2m") or []
    pprob = hourly.get("precipitation_probability") or []

    t_now = cur.get("temperature_2m")
    wind = cur.get("wind_speed_10m")
    rh = cur.get("relative_humidity_2m")

    # оценим дневной мин/макс
    t_min = min(temps) if temps else None
    t_max = max(temps) if temps else None
    p_day = max(pprob) if pprob else None

    if lang == "uk":
        head = f"Погода у {show_name}: "
        now = f"зараз {t_now}°C" if t_now is not None else "дані відсутні"
        wind_s = f", вітер {wind} м/с" if wind is not None else ""
        hum_s = f", вологість {rh}%" if rh is not None else ""
        day = ""
        if t_min is not None and t_max is not None:
            day = f". Сьогодні {round(t_min,1)}…{round(t_max,1)}°C"
        rain = f", опади {p_day}%" if p_day is not None else ""
        return head + now + wind_s + hum_s + day + rain + "."
    else:
        head = f"Погода в {show_name}: "
        now = f"сейчас {t_now}°C" if t_now is not None else "данные отсутствуют"
        wind_s = f", ветер {wind} м/с" if wind is not None else ""
        hum_s = f", влажность {rh}%" if rh is not None else ""
        day = ""
        if t_min is not None and t_max is not None:
            day = f". Сегодня {round(t_min,1)}…{round(t_max,1)}°C"
        rain = f", осадки {p_day}%" if p_day is not None else ""
        return head + now + wind_s + hum_s + day + rain + "."

# ---------- Праздники сегодня ----------
async def holidays_today(country_code: str = "UA") -> List[Dict[str, Any]]:
    """Возвращает список праздников на сегодня (локальные названия, если есть)."""
    now = datetime.now(timezone.utc)
    year = now.year
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    async with aiohttp.ClientSession() as session:
        try:
            data = await _fetch_json(session, url)
        except Exception:
            return []
    today = now.date().isoformat()
    return [x for x in (data or []) if (x.get("date") == today)]

# ---------- Примитивный веб-поиск (DuckDuckGo через proxy) ----------
_RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S
)

def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)

async def web_search(query: str, lang: str = "ru", limit: int = 3) -> str:
    """Очень простой поиск (топ-N ссылок) без ключей. Для продакшена лучше Google CSE/SerpAPI."""
    q = query.strip()
    if not q:
        return "Пустой запрос."
    url = f"https://r.jina.ai/http://duckduckgo.com/html/?q={quote(q)}"
    async with aiohttp.ClientSession() as session:
        try:
            text = await _fetch_text(session, url)
        except Exception as e:
            return f"⚠️ Ошибка поиска: {e}"
    items = []
    for href, title_html in _RESULT_RE.findall(text):
        title = _strip_tags(title_html)
        if not title or not href.startswith(("http://", "https://")):
            continue
        items.append((title, href))
        if len(items) >= limit:
            break
    if not items:
        return "Ничего не найдено."
    label = "Результати пошуку:" if lang == "uk" else "Результаты поиска:"
    lines = [label]
    for i, (t, u) in enumerate(items, 1):
        lines.append(f"{i}) {t}\n{u}")
    return "\n".join(lines)
