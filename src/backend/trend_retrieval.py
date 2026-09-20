"""
Trend/context retrieval -- Session 4 stub, Session 5 real wiring.

get_mock_context() returns placeholder trend data so the rest of the
pipeline can be built and tested before Google Trends / festival-calendar
integrations are wired in.

get_weather() is already a REAL working call (Open-Meteo, no API key
required), so the team has at least one live, grounded signal from week one.
"""

from typing import Optional
import requests

# crude city -> lat/lon lookup for early demo regions; expand as you lock
# in your actual 3-4 US states and 3-4 India states/cities
CITY_COORDS = {
    "austin": (30.27, -97.74),
    "minneapolis": (44.98, -93.27),
    "miami": (25.76, -80.19),
    "mumbai": (19.08, 72.88),
    "delhi": (28.61, 77.21),
    "chennai": (13.08, 80.27),
}


def get_weather(city: Optional[str]) -> str:
    if not city:
        return "unknown (no city provided)"
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
    to this country/region, plus a relevance-ranking step (see design doc --
    this is the "Relevance Ranker" component in the architecture).
    """
    return f"[placeholder trend for {region}, {country} -- wire up Google Trends here]"


def get_mock_context(country: str, region: str, city: Optional[str]) -> dict:
    return {
        "trend": get_trend_stub(country, region),
        "weather": get_weather(city),
    }
