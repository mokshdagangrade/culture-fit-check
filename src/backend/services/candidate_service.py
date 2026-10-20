"""
Stage 1 of signal retrieval: narrow a day's signals down to a short,
balanced, safe candidate pool for one state.

The cleaning notebook unifies all eight sources into `signal_candidate`
(one row = one text signal, state-tagged, deduped, noise-flagged). On a
given day that is ~750 rows per state, and for Texas on 2026-10-20 it was
1,315 of which 1,000 were Ticketmaster events. Handing that to anything
downstream is useless, so this module does the cheap, deterministic
narrowing before any model is involved:

    state + national  ->  fresh  ->  not dup/noise  ->  safe  ->  per-source quota

No embeddings here on purpose. The retrieval key is structured (state and
date), and lexical similarity between a brand brief and a 40-character
signal title does not work -- measured on the real snapshot, the best
cosine match for a coffee-launch brief was 0.037, matching the word
"friends" in the event title "Alvin Perry & Friends". Judging which signal
suits a brand is reasoning, not similarity, so that is left to
ranker_service.

Quotas matter more than they look. Without them, events (73% of all rows)
fill every slot.
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone

from pymongo.errors import PyMongoError

from db import signal_candidates_collection
from regions import STATE_CODES_BY_NAME
from services.trend_service import unsafe_reason

logger = logging.getLogger(__name__)

# How many of each source may enter the pool the ranker sees. Tuned so no
# single source can dominate; totals ~45, trimmed to POOL_SIZE below.
SOURCE_QUOTA = {
    "trends": 8,
    "news": 8,
    "social": 8,
    "events": 10,
    "calendar": 4,
    "sports": 3,
    "youtube": 2,
    "attention": 2,
}

POOL_SIZE = 40          # hard cap on candidates handed to the ranker
LOOKBACK_DAYS = 2       # how far back to accept a snapshot before calling it stale


def _fields(doc: dict) -> dict:
    """The only fields anything downstream should see."""
    return {
        "signal_id": doc.get("signal_id"),
        "source": doc.get("source"),
        "text": str(doc.get("text") or "")[:500],
        "context": str(doc.get("context") or "")[:500],
        "geo_scope": doc.get("geo_scope"),
        "geo_confidence": doc.get("geo_confidence"),
        "date": doc.get("date"),
        "event_date": doc.get("event_date"),
        "is_national": bool(doc.get("is_national")),
    }


def get_candidate_pool(state: str, today: date | None = None) -> dict:
    """
    Returns {"as_of", "stale_days", "pool", "refused", "counts"} for one state.

    `pool` is the balanced, safe shortlist. `refused` records every signal the
    safety gate dropped, with its reason, so the block rate stays measurable.
    An empty pool is normal (no snapshot loaded yet) and callers must cope.
    """
    code = STATE_CODES_BY_NAME.get(state)
    if not code:
        return {"as_of": None, "stale_days": None, "pool": [], "refused": [], "counts": {}}

    today = today or datetime.now(timezone.utc).date()
    earliest = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()

    try:
        docs = list(signal_candidates_collection.find(
            {
                "date": {"$gte": earliest, "$lte": today.isoformat()},
                "$or": [{"state_code": code}, {"is_national": True}],
                "is_dup": False,
                "is_noise": False,
                "is_within_window": True,
            },
            {"_id": 0},
        ).sort([("date", -1), ("position", 1)]))
    except PyMongoError:
        logger.warning("Signal candidates unavailable for %s", code)
        return {"as_of": None, "stale_days": None, "pool": [], "refused": [], "counts": {}}

    if not docs:
        return {"as_of": None, "stale_days": None, "pool": [], "refused": [], "counts": {}}

    # Use one day only -- mixing days would present stale signals as current.
    as_of = docs[0]["date"]
    docs = [d for d in docs if d.get("date") == as_of]

    # Prefer current/upcoming holidays before the calendar quota fills.
    def calendar_priority(doc):
        if doc.get("source") != "calendar":
            return (1, 0, 0)
        days = doc.get("days_from_date")
        if not isinstance(days, (int, float)) or not math.isfinite(days):
            return (0, 2, 0)
        return (0, int(days < 0), abs(days))

    docs.sort(key=calendar_priority)
    pool, refused, used = [], [], {}
    for doc in docs:
        if doc.get("geo_confidence") == "unreliable":
            continue
        reason = unsafe_reason({"keyword": doc.get("text") or "",
                                "news_headline": doc.get("context") or ""})
        if reason:
            refused.append({"signal_id": doc.get("signal_id"),
                            "source": doc.get("source"),
                            "text": doc.get("text"),
                            "reason": reason})
            continue
        source = doc.get("source")
        if used.get(source, 0) >= SOURCE_QUOTA.get(source, 1):
            continue
        used[source] = used.get(source, 0) + 1
        pool.append(_fields(doc))

    # Interleave so the cap doesn't truncate whole sources off the end.
    pool = _interleave(pool)[:POOL_SIZE]

    return {
        "as_of": as_of,
        "stale_days": (today - date.fromisoformat(as_of)).days,
        "pool": pool,
        "refused": refused,
        "counts": {source: sum(p["source"] == source for p in pool)
                   for source in sorted({p["source"] for p in pool})},
    }


def _interleave(pool: list) -> list:
    """Round-robin across sources, so a truncation loses the tail of every
    source evenly instead of deleting the last source outright."""
    by_source: dict[str, list] = {}
    for item in pool:
        by_source.setdefault(item["source"], []).append(item)
    ordered, rank = [], 0
    while any(by_source.values()):
        for source in sorted(by_source):
            if rank < len(by_source[source]):
                ordered.append(by_source[source][rank])
        rank += 1
        if rank > max(len(v) for v in by_source.values()):
            break
    return ordered