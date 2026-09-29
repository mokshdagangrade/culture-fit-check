from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import WeatherDoc, SourceMeta, GeoTag

BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> a short human-readable label. Not exhaustive,
# but covers the common ones. Anything unmapped stays as the raw code.
WMO_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "light showers", 81: "showers", 82: "violent showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}


def fetch_weather(state: dict, timeout: int = 10) -> WeatherDoc:
    params = {
        "latitude": state["lat"],
        "longitude": state["lon"],
        "current": "temperature_2m,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    current = body.get("current", {})
    daily = body.get("daily", {})
    code = current.get("weather_code")

    return WeatherDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(source="open-meteo", url=resp.url, fetched_at=datetime.now(timezone.utc)),
        geo=GeoTag(scope="state", state_code=state["code"], confidence="exact"),
        temperature_c=current.get("temperature_2m"),
        temperature_max_c=(daily.get("temperature_2m_max") or [None])[0],
        temperature_min_c=(daily.get("temperature_2m_min") or [None])[0],
        precipitation_mm=current.get("precipitation"),
        weather_code=code,
        condition=WMO_CODES.get(code),
    )
