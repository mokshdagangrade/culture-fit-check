import os
from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import EventsDoc, EventItem, SourceMeta, GeoTag

BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


class MissingAPIKey(Exception):
    pass


def fetch_events(state: dict, size: int = 50, timeout: int = 10) -> EventsDoc:
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        raise MissingAPIKey(
            "TICKETMASTER_API_KEY is not set. Get a free key at "
            "developer.ticketmaster.com and add it to .env."
        )

    params = {
        "apikey": api_key,
        "stateCode": state["code"],
        "countryCode": "US",
        "size": size,
        "sort": "date,asc",
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    raw_events = body.get("_embedded", {}).get("events", [])
    events = []
    for e in raw_events:
        venue = (e.get("_embedded", {}).get("venues") or [{}])[0]
        classifications = (e.get("classifications") or [{}])[0]
        segment = (classifications.get("segment") or {}).get("name")
        genre = (classifications.get("genre") or {}).get("name")
        price_ranges = (e.get("priceRanges") or [{}])[0]

        events.append(EventItem(
            name=e.get("name", ""),
            url=e.get("url"),
            start_date=(e.get("dates", {}).get("start") or {}).get("localDate"),
            venue_name=venue.get("name"),
            venue_city=(venue.get("city") or {}).get("name"),
            venue_state=(venue.get("state") or {}).get("stateCode"),
            classification=segment,
            genre=genre,
            price_min=price_ranges.get("min"),
            price_max=price_ranges.get("max"),
        ))

    safe_url = resp.url.replace(api_key, "REDACTED")

    return EventsDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(
            source="ticketmaster", url=safe_url, fetched_at=datetime.now(timezone.utc),
            status="empty" if not events else "ok",
        ),
        geo=GeoTag(scope="state", state_code=state["code"], confidence="exact"),
        events=events,
    )