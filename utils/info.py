# utils/info.py
import aiohttp
from datetime import datetime
from typing import Optional

async def geocode(city: str, lang: str = "ru") -> Optional[dict]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "uk" if lang=="uk" else "ru", "format": "json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                return None
            data = await r.json()
    if not data.get("results"):
        return None
    r = data["results"][0]
    return {"lat": r["latitude"], "lon": r["longitude"], "name": r.get("name")}

async def weather_today(city: str, lang: str = "ru") -> str:
    g = await geocode(city, lang)
    if not g:
        return ("Не нашёл город." if lang=="ru" else "Місто не знайдено.") + f" {city}"
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": g["lat"], "longitude": g["lon"],
        "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
    }
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                return "Ошибка погоды" if lang=="ru" else "Помилка погоди"
            data = await r.json()
    cur = data.get("current", {})
    daily = data.get("daily", {})
    t = cur.get("temperature_2m")
    w = cur.get("wind_speed_10m")
    rh = cur.get("relative_humidity_2m")
    tmax = (daily.get("temperature_2m_max") or [None])[0]
    tmin = (daily.get("temperature_2m_min") or [None])[0]
    popmax = (daily.get("precipitation_probability_max") or [None])[0]
    if lang=="uk":
        return f"Погода у {g['name']}: зараз {t}°C, вітер {w} м/с, вологість {rh}%. Сьогодні {tmin}…{tmax}°C, опади {popmax}%."
    else:
        return f"Погода в {g['name']}: сейчас {t}°C, ветер {w} м/с, влажность {rh}%. Сегодня {tmin}…{tmax}°C, осадки {popmax}%."

async def holidays_today(country: str) -> list[dict]:
    dt = datetime.utcnow().date()
    url = f"https://date.nager.at/api/v3/PublicHolidays/{dt.year}/{country}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=20) as r:
            if r.status != 200:
                return []
            arr = await r.json()
    today_iso = dt.isoformat()
    return [h for h in arr if h.get("date") == today_iso]
