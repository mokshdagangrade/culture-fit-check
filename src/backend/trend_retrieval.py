"""
Trend/context retrieval -- still a Session 4/5 stub for trend, real for weather.

get_weather() is a REAL working call (Open-Meteo, no API key required).
get_trend_stub() is a placeholder -- wire up Google Trends here next.

Since users now select STATES (not cities) in their profile, STATE_TO_CITY
maps each supported state to a representative city for the weather lookup.
Expand both dicts as you lock in more launch states.
"""

from typing import Optional
import requests

CITY_COORDS = {
    "austin": (30.27, -97.74),
    "minneapolis": (44.98, -93.27),
    "miami": (25.76, -80.19),
    "mumbai": (19.08, 72.88),
    "delhi": (28.61, 77.21),
    "chennai": (13.08, 80.27),
}

STATE_TO_CITY = {
    "texas": "austin",
    "minnesota": "minneapolis",
    "florida": "miami",
    "maharashtra": "mumbai",
    "delhi": "delhi",
    "tamil nadu": "chennai",
}


def get_weather(city: Optional[str]) -> str:
    if not city:
        return "unknown (no city mapped for this region yet)"
    coords = CITY_COORDS.get(city.lower())
    if not coords:
        return f"unknown ({city} not in coord table yet -- add it to CITY_COORDS)"
    lat, lon = coords
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=5,
        )
        resp.raise_for_status()
        weather = resp.json().get("current_weather", {})
        return f"{weather.get('temperature')}C, windspeed {weather.get('windspeed')} km/h"
    except requests.RequestException as e:
        return f"weather lookup failed: {e}"


def get_trend_stub(country: str, region: str) -> str:
    """
    TODO (Session 5): replace with a real Google Trends API call filtered
    to this country/region, plus a relevance-ranking step.
    """
    return f"[placeholder trend for {region}, {country} -- wire up Google Trends here]"


def get_mock_context(country: str, region: str, city: Optional[str] = None) -> dict:
    resolved_city = city or STATE_TO_CITY.get(region.lower())
    return {
        "trend": get_trend_stub(country, region),
        "weather": get_weather(resolved_city),
    }
