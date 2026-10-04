"""Read recent, bounded state API responses from the existing data pipeline."""
from datetime import datetime, timedelta, timezone
import logging
from pymongo.errors import PyMongoError
from db import state_signals_collection
from regions import STATE_CODES_BY_NAME

logger = logging.getLogger(__name__)
FIELDS = {
    "weather": {"condition", "temperature_c", "temperature_max_c", "temperature_min_c", "precipitation_mm", "weather_code"},
    "trends": {"trends"},
    "news": {"articles"},
    "calendar": {"holidays_today", "holidays_this_month"},
    "events": {"events"},
    "social": {"subreddit", "subreddit_confirmed", "posts"},
    "sports": {"league", "events"},
    "attention": {"project", "top_articles"},
    "youtube": {"videos"},
}
NATIONAL_SOURCES = {"sports", "attention", "youtube"}


def compact(value):
    """Bound source payloads without passing metadata URLs or credentials."""
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return [compact(item) for item in value[:10]]
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items()
                if key not in ("meta", "url") and item is not None}
    return value


def get_state_context(state, now=None):
    code = STATE_CODES_BY_NAME.get(state)
    if not code:
        return {}
    today = (now or datetime.now(timezone.utc)).date()
    try:
        doc = state_signals_collection.find_one({
            "state_code": code,
            "date": {"$gte": (today - timedelta(days=1)).isoformat(), "$lte": today.isoformat()},
        }, sort=[("date", -1)])
    except PyMongoError:
        logger.warning("State context unavailable for %s", code)
        return {}
    if not doc:
        return {}
    context = {}
    for source, fields in FIELDS.items():
        signal = (doc.get("signals") or {}).get(source)
        if not isinstance(signal, dict) or signal.get("meta", {}).get("status") != "ok":
            continue
        geo = signal.get("geo") or {}
        scope = geo.get("scope") or signal.get("scope", "state")
        confidence = geo.get("confidence", "inferred")
        if confidence == "unreliable":
            continue
        if source in NATIONAL_SOURCES:
            if scope != "national" or signal.get("country_code", "US") != "US":
                continue
        elif signal.get("state_code") != code or scope not in ("state", "city"):
            continue
        if source == "social":
            if not signal.get("subreddit_confirmed"):
                continue
        elif confidence == "guessed":
            continue
        values = {key: compact(signal[key]) for key in sorted(fields)
                  if signal.get(key) is not None and signal[key] != []}
        # Social metadata alone does not constitute content.
        if source == "social" and not values.get("posts"):
            continue
        if values:
            context[source] = {"data": values, "date": doc["date"],
                               "source": signal.get("meta", {}).get("source"),
                               "scope": scope, "confidence": confidence}
    return context
