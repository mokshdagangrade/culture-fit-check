import os
from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import CalendarDoc, Holiday, SourceMeta

BASE_URL = "https://calendarific.com/api/v2/holidays"


class MissingAPIKey(Exception):
    pass


def fetch_holidays(state: dict, timeout: int = 10) -> CalendarDoc:
    api_key = os.environ.get("CALENDARIFIC_API_KEY")
    if not api_key:
        raise MissingAPIKey(
            "CALENDARIFIC_API_KEY is not set. Get a free key at "
            "calendarific.com and add it to .env."
        )

    today = date.today()
    params = {
        "api_key": api_key,
        "country": "US",
        "location": f"us-{state['code'].lower()}",   # Calendarific's ISO 3166-2 style subdivision code
        "year": today.year,
        "month": today.month,
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    raw = body.get("response", {}).get("holidays", [])
    all_holidays = [
        Holiday(
            name=h["name"],
            date=h["date"]["iso"],
            type=(h.get("type") or [None])[0],
            state_specific="Local" in (h.get("type") or []) or "State" in (h.get("type") or []),
        )
        for h in raw
    ]
    today_iso = today.isoformat()
    today_holidays = [h for h in all_holidays if h.date.startswith(today_iso)]

    safe_url = resp.url.replace(api_key, "REDACTED")

    return CalendarDoc(
        state_code=state["code"],
        date=today,
        meta=SourceMeta(
            source="calendarific",
            url=safe_url,
            fetched_at=datetime.now(timezone.utc),
            status="empty" if not all_holidays else "ok",
        ),
        holidays_today=today_holidays,
        holidays_this_month=all_holidays,
    )
