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
    CalendarDoc, SocialDoc, SportsDoc, StitchedDoc, StitchedSignals,
)
from us_states import US_STATES

_STATE_BY_CODE = {s["code"]: s for s in US_STATES}

_SOURCE_NAMES = ("weather", "news", "trends", "attention", "calendar", "social", "sports")


def stitch_state(
    state_code: str,
    the_date,
    weather: Optional[WeatherDoc] = None,
    news: Optional[NewsDoc] = None,
    trends: Optional[TrendsDoc] = None,
    attention: Optional[AttentionDoc] = None,
    calendar: Optional[CalendarDoc] = None,
    social: Optional[SocialDoc] = None,
    sports: Optional[SportsDoc] = None,
) -> StitchedDoc:
    state = _STATE_BY_CODE[state_code]
    docs = {
        "weather": weather, "news": news, "trends": trends,
        "attention": attention, "calendar": calendar, "social": social, "sports": sports,
    }

    present = [name for name in _SOURCE_NAMES if docs[name] is not None]
    missing = [name for name in _SOURCE_NAMES if docs[name] is None]

    return StitchedDoc(
        state_code=state_code,
        state_name=state["name"],
        region=state["region"],
        date=the_date,
        stitched_at=datetime.now(timezone.utc),
        sources_present=present,
        sources_missing=missing,
        signals=StitchedSignals(**docs),
    )
