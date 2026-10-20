"""Combine state-level sources only. National data stays in its own snapshot."""

from datetime import datetime, timezone

from schemas import ErrorDoc, StitchedDoc, StitchedSignals
from us_states import US_STATES

_STATE_BY_CODE = {state["code"]: state for state in US_STATES}


def stitch_state(state_code, the_date, weather=None, news=None, trends=None,
                 calendar=None, social=None, events=None) -> StitchedDoc:
    state = _STATE_BY_CODE[state_code]
    sources = {"weather": weather, "news": news, "trends": trends,
               "calendar": calendar, "social": social, "events": events}
    sources = {name: None if isinstance(doc, ErrorDoc) else doc for name, doc in sources.items()}
    return StitchedDoc(
        state_code=state_code, state_name=state["name"],
        census_region=state["census_region"], census_division=state["census_division"],
        date=the_date, stitched_at=datetime.now(timezone.utc),
        sources_present=[name for name, doc in sources.items() if doc is not None],
        sources_missing=[name for name, doc in sources.items() if doc is None],
        signals=StitchedSignals(**sources),
    )
