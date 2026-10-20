"""
Runs the full pipeline for one day, for all 50 US states
"""

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from schemas import ErrorDoc

load_dotenv()

from us_states import US_STATES
from extractors.weather import fetch_weather
from extractors.news import fetch_news
from extractors.trends import fetch_trends
from extractors.attention import fetch_top_attention
from extractors.calendar import fetch_calendar_batch
from extractors.social import fetch_subreddit_posts
from extractors.sports import fetch_scoreboard
from extractors.events import fetch_events
from extractors.youtube import fetch_trending
from stitch import stitch_state
from validate import check_reference_data, check_batch
from signal_windows import DEFAULT_WINDOWS_PATH, load_windows, window_settings

OUT_DIR = Path(__file__).parent / "out"


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    temporary.replace(path)


def try_fetch(label, fn, *args, **kwargs):
    """Run one extractor call; on failure, print why and return an
    ErrorDoc rather than crashing the whole 50-state run."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        message = re.sub(r"(?i)((?:api_?key|key|access_token)=)[^&\s]+", r"\1REDACTED", str(e))
        print(f"  [skip] {label}: {message}")
        return ErrorDoc(source=label, error=message, fetched_at=datetime.now(timezone.utc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only process the first N states")
    parser.add_argument("--windows", type=Path, default=DEFAULT_WINDOWS_PATH, help="JSON age windows for every source")
    parser.add_argument("--calendar-cache-days", type=int, default=30)
    parser.add_argument("--refresh-calendar", action="store_true", help="refresh cached country calendars")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 50:
        parser.error("--limit must be between 1 and 50")
    if args.calendar_cache_days < 1:
        parser.error("--calendar-cache-days must be positive")
    windows = load_windows(args.windows)
    print("Age windows are checked during cleaning; they do not guarantee complete API history or forecasts.")

    ref_errors = check_reference_data()
    if ref_errors:
        print("Reference data errors -- fix us_states.py before running:")
        for e in ref_errors:
            print(f"  - {e}")
        return

    today = date.today()
    states = US_STATES[: args.limit] if args.limit else US_STATES
    OUT_DIR.mkdir(exist_ok=True)

    print(f"Fetching national-level sources for {today}...")
    attention_doc = try_fetch("attention", fetch_top_attention, max_days_back=windows["attention"].lookback_days)
    sports_doc = try_fetch("sports (ESPN)", fetch_scoreboard, window=windows["sports"], reference_date=today)
    youtube_doc = try_fetch("youtube (trending)", fetch_trending)
    calendars = try_fetch("calendar", fetch_calendar_batch, states, reference_date=today,
                          window=windows["calendar"], cache_days=args.calendar_cache_days,
                          refresh=args.refresh_calendar)
    if isinstance(calendars, ErrorDoc):
        state_calendars, national_calendar = {}, None
    else:
        state_calendars, national_calendar = calendars
    run_id = uuid4().hex
    national_docs = {"attention": attention_doc, "sports": sports_doc, "youtube": youtube_doc}
    national = {"date": today.isoformat(), "country_code": "US", "run_id": run_id,
                "windows": window_settings(windows), "signals": {"calendar": national_calendar},
                "source_errors": {}}
    for source, doc in national_docs.items():
        if isinstance(doc, ErrorDoc):
            national["source_errors"][source] = doc.model_dump(mode="json")
        else:
            national["signals"][source] = doc.model_dump(mode="json")
    if isinstance(calendars, ErrorDoc):
        national["source_errors"]["calendar"] = calendars.model_dump(mode="json")

    stitched_docs = []
    state_payloads = []
    for i, state in enumerate(states):
        print(f"[{i+1}/{len(states)}] {state['name']} ({state['code']})")

        weather_doc = try_fetch("weather", fetch_weather, state)
        news_doc = try_fetch("news", fetch_news, state)
        calendar_doc = state_calendars.get(state["code"], calendars if isinstance(calendars, ErrorDoc) else None)
        social_doc = try_fetch("social", fetch_subreddit_posts, state)
        trends_doc = try_fetch("trends", fetch_trends, state)
        events_doc = try_fetch("events", fetch_events, state, window=windows["events"], reference_date=today)

        stitched = stitch_state(
            state_code=state["code"], the_date=today,
            weather=weather_doc, news=news_doc, trends=trends_doc,
            calendar=calendar_doc, social=social_doc,
            events=events_doc,
        )
        stitched_docs.append(stitched)
        payload = stitched.model_dump(mode="json")
        payload["country_code"] = "US"
        payload["run_id"] = run_id
        state_sources = {"weather": weather_doc, "news": news_doc, "social": social_doc,
                         "trends": trends_doc, "events": events_doc, "calendar": calendar_doc}
        payload["source_errors"] = {source: doc.model_dump(mode="json") for source, doc in state_sources.items()
                                    if isinstance(doc, ErrorDoc)}
        state_payloads.append(payload)

    report = check_batch(stitched_docs, expected_date=today)
    print("\nValidation report:")
    print(json.dumps(report, indent=2, default=str))

    out_file = OUT_DIR / f"state_signals_daily_{today.isoformat()}.json"
    write_json(OUT_DIR / f"national_signals_daily_{today.isoformat()}.json", national)
    write_json(out_file, state_payloads)
    print(f"\nWrote {len(stitched_docs)} stitched documents to {out_file}")

    if not report["ok"]:
        print("\nValidation found errors -- review before loading into Mongo.")


if __name__ == "__main__":
    main()
