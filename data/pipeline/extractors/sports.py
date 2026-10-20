from datetime import date, datetime, timedelta, timezone

from http_client import polite_get
from schemas import SportsDoc, SportsEvent, SourceMeta
from signal_windows import SignalWindow

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUES = {
    "nfl": "football/nfl",
    "college-football": "football/college-football",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "mens-college-basketball": "basketball/mens-college-basketball",
    "womens-college-basketball": "basketball/womens-college-basketball",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "mls": "soccer/usa.1",
}


def fetch_scoreboard(timeout: int = 10, window=None, reference_date=None) -> SportsDoc:
    reference_date = reference_date or date.today()
    start, end = (window or SignalWindow(0, 4)).bounds(reference_date)
    events, urls, errors, league_status = [], [], [], {}
    seen = set()

    for league, path in LEAGUES.items():
        n_before = len(events)
        failed = False
        for offset in range((end - start).days + 1):
            game_date = start + timedelta(days=offset)
            params = {"dates": game_date.strftime("%Y%m%d"), "limit": 1000}
            if "college" in league:
                params["groups"] = 50
            try:
                resp = polite_get(f"{BASE_URL}/{path}/scoreboard", params=params, timeout=timeout)
                resp.raise_for_status()
                body = resp.json()
                raw_events = body["events"]
                urls.append(resp.url)
                if len(raw_events) >= params["limit"]:
                    errors.append(f"{league} {game_date}: result limit reached; coverage may be incomplete")
                for event in raw_events:
                    start_time = event.get("date")
                    if start_time:
                        game_day = datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(timezone.utc).date()
                        if not start <= game_day <= end:
                            continue
                    event_id = event.get("id")
                    key = (league, event_id)
                    if event_id and key in seen:
                        continue
                    if event_id:
                        seen.add(key)
                    comp = (event.get("competitions") or [{}])[0]
                    competitors = comp.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
                    venue = comp.get("venue") or {}
                    address = venue.get("address") or {}
                    events.append(SportsEvent(
                        league=league, event_id=event_id,
                        home_team=(home.get("team") or {}).get("displayName"),
                        away_team=(away.get("team") or {}).get("displayName"),
                        venue_name=venue.get("fullName"), venue_city=address.get("city"),
                        venue_state=address.get("state"), start_time=start_time,
                        status=(event.get("status") or {}).get("type", {}).get("description"),
                    ))
            except Exception as exc:
                failed = True
                errors.append(f"{league} {game_date}: {exc}")
                print(f"  [sports] {league} {game_date}: {exc}")
        league_status[league] = "error" if failed else "ok" if len(events) > n_before else "empty"

    return SportsDoc(
        date=reference_date, league_status=league_status,
        meta=SourceMeta(
            source="espn", url=";".join(urls) or BASE_URL, fetched_at=datetime.now(timezone.utc),
            status="ok" if events else "error" if errors else "empty",
            error="; ".join(errors) or None,
        ),
        events=events,
    )
