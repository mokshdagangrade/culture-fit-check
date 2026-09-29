"""
Runs the full pipeline for one day, for all 50 US states
"""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from schemas import ErrorDoc

load_dotenv()

from us_states import US_STATES
from extractors.weather import fetch_weather
from extractors.news import fetch_news
from extractors.trends import fetch_trends
from extractors.attention import fetch_top_attention
from extractors.calendar import fetch_holidays, MissingAPIKey as CalendarKeyMissing
from extractors.social import fetch_subreddit_posts
from extractors.sports import fetch_scoreboard
from extractors.events import fetch_events
from extractors.youtube import fetch_trending
from stitch import stitch_state
from validate import check_reference_data, check_batch

OUT_DIR = Path(__file__).parent / "out"


def try_fetch(label, fn, *args, **kwargs):
    """Run one extractor call; on failure, print why and return an
    ErrorDoc rather than crashing the whole 50-state run."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"  [skip] {label}: {e}")
        return ErrorDoc(source=label, error=str(e), fetched_at=datetime.now(timezone.utc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only process the first N states")
    args = parser.parse_args()

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
    attention_doc = try_fetch("attention (Wikipedia)", fetch_top_attention)
    sports_doc = try_fetch("sports (ESPN)", fetch_scoreboard)
    youtube_doc = try_fetch("youtube (trending)", fetch_trending)

    stitched_docs = []
    for i, state in enumerate(states):
        print(f"[{i+1}/{len(states)}] {state['name']} ({state['code']})")

        weather_doc = try_fetch("weather", fetch_weather, state)
        news_doc = try_fetch("news", fetch_news, state)
        calendar_doc = try_fetch("calendar", fetch_holidays, state)
        social_doc = try_fetch("social", fetch_subreddit_posts, state)
        trends_doc = try_fetch("trends", fetch_trends, state)
        events_doc = try_fetch("events", fetch_events, state)

        stitched = stitch_state(
            state_code=state["code"], the_date=today,
            weather=weather_doc, news=news_doc, trends=trends_doc,
            attention=attention_doc,
            calendar=calendar_doc, social=social_doc, sports=sports_doc,
            events=events_doc, youtube=youtube_doc,
        )
        stitched_docs.append(stitched)

    report = check_batch(stitched_docs, expected_date=today)
    print("\nValidation report:")
    print(json.dumps(report, indent=2, default=str))

    out_file = OUT_DIR / f"state_signals_daily_{today.isoformat()}.json"
    with open(out_file, "w") as f:
        json.dump([d.model_dump(mode="json") for d in stitched_docs], f, indent=2, default=str)
    print(f"\nWrote {len(stitched_docs)} stitched documents to {out_file}")

    if not report["ok"]:
        print("\nValidation found errors -- review before loading into Mongo.")


if __name__ == "__main__":
    main()
