from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import SportsDoc, SportsEvent, SourceMeta

SCOREBOARD_URL = "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"


def fetch_scoreboard(league: str = "college-football", timeout: int = 10) -> SportsDoc:
    # College sports truncate to a short list by default. groups=50
    # (all Division I) + a high limit gets the full day's slate --
    # confirmed against https://github.com/pseudo-r/Public-ESPN-API,
    # whose own test found 12 events without these params vs. 36 with them.
    params = {"groups": 50, "limit": 500}
    resp = polite_get(SCOREBOARD_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    events = []
    for e in body.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        venue = comp.get("venue", {})
        address = venue.get("address", {})

        events.append(SportsEvent(
            home_team=(home.get("team") or {}).get("displayName"),
            away_team=(away.get("team") or {}).get("displayName"),
            venue_name=venue.get("fullName"),
            venue_city=address.get("city"),
            venue_state=address.get("state"),
            start_time=e.get("date"),
            status=(e.get("status") or {}).get("type", {}).get("description"),
        ))

    return SportsDoc(
        league=league,
        date=date.today(),
        meta=SourceMeta(
            source="espn", url=resp.url, fetched_at=datetime.now(timezone.utc),
            status="empty" if not events else "ok",
        ),
        events=events,
    )
