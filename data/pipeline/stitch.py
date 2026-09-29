"""
Joins raw per-source documents into one StitchedDoc per state, for a
given date. The join key is state_code (+ date).

attention and sports are national-level (see their extractors), so
the *same* AttentionDoc/SportsDoc instance is passed in for every
state -- they are not re-fetched per state.

This does not talk to Mongo -- it operates on whatever raw docs the
caller already has in memory, and returns StitchedDoc objects ready
to insert into `state_signals_daily`.
"""

from datetime import timezone, datetime
from typing import Optional

from schemas import (
    WeatherDoc, NewsDoc, TrendsDoc, AttentionDoc,
    CalendarDoc, SocialDoc, SportsDoc, EventsDoc, YoutubeDoc,
    ErrorDoc, StitchedDoc, StitchedSignals,
)
from us_states import US_STATES

_STATE_BY_CODE = {s["code"]: s for s in US_STATES}

_SOURCE_NAMES = ("weather", "news", "trends", "attention", "calendar", "social", "sports", "events", "youtube")


def stitch_state(
    state_code: str,
    the_date,
    weather=None, news=None, trends=None,
    attention=None, calendar=None, social=None, sports=None,
    events=None, youtube=None,
) -> StitchedDoc:
    state = _STATE_BY_CODE[state_code]
    docs = {
        "weather": weather, "news": news, "trends": trends,
        "attention": attention, "calendar": calendar, "social": social, "sports": sports,
        "events": events, "youtube": youtube,
    }
    docs = {name: (None if isinstance(doc, ErrorDoc) else doc) for name, doc in docs.items()}

    present = [name for name in _SOURCE_NAMES if docs[name] is not None]
    missing = [name for name in _SOURCE_NAMES if docs[name] is None]

    return StitchedDoc(
        state_code=state_code,
        state_name=state["name"],
        census_region=state["census_region"],
        census_division=state["census_division"],
        date=the_date,
        stitched_at=datetime.now(timezone.utc),
        sources_present=present,
        sources_missing=missing,
        signals=StitchedSignals(**docs),
    )
