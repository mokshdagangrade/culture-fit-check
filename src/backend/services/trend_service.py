"""
Selects which of a state's trending searches are usable as marketing hooks.

The data pipeline (data/pipeline/extractors/trends.py) writes Google
"Trending now" items per US state into state_signals_daily. Those items are
whatever the state is searching right now, which on any given day is mostly
news: deaths, shootings, wildfires, elections. Handing those to a copy
generator unfiltered is the worst failure this product has -- a brand making
a joke next to a tragedy.

So this module does two things: drop the unusable trends, and rank what is
left. It is the gate between "what is trending" and "what we will write
about".

On the filter: it is keyword matching, not understanding. It cannot catch a
named politician, a local tragedy phrased obliquely, or sarcasm, and it will
drop benign trends that happen to share a word. That trade is deliberate --
a dropped good trend costs one suggestion, a kept bad one costs a customer
their reputation. Every drop is recorded with its reason so the block rate
can be measured against real traffic and this can be replaced by a trained
classifier once there is data to train one on.
"""

import re
from typing import Optional

SENSITIVE_TERMS: dict[str, tuple[str, ...]] = {
    "death": (
        "died", "dies", "dead", "death", "deaths", "obituary", "obit", "funeral",
        "passed away", "killed", "kills", "fatal", "fatality", "fatalities",
        "body found", "remembering", "tribute", "memorial", "mourning",
    ),
    "violence": (
        "shooting", "shootings", "shooter", "shots fired", "gunman", "gun", "guns",
        "stabbing", "stabbed", "murder", "homicide", "assault", "attack", "attacked",
        "hostage", "bomb", "bombing", "explosion", "terror", "terrorist", "war",
        "airstrike", "missile", "massacre",
    ),
    "disaster": (
        "wildfire", "wildfires", "house fire", "brush fire", "hurricane", "tornado",
        "flood", "flooding", "earthquake", "evacuate", "evacuation", "evacuations",
        "disaster", "emergency", "storm warning", "tsunami", "landslide",
        "goes missing", "missing person",
    ),
    "crime": (
        "arrest", "arrested", "charged", "indicted", "indictment", "lawsuit", "sued",
        "trial", "verdict", "guilty", "convicted", "police", "sheriff",
        "investigation", "scandal", "fraud", "abuse", "trafficking", "manhunt",
        "suspect", "assaulted",
    ),
    "politics": (
        "election", "elections", "ballot", "vote", "votes", "voting", "primary",
        "campaign", "senate", "senator", "congress", "congressman", "congresswoman",
        "governor", "president", "presidential", "mayor", "impeach", "impeachment",
        # "rally" alone is not political enough -- it drops sports comebacks,
        # pep rallies and market rallies, which are good hooks.
        "shutdown", "protest", "protests", "campaign rally", "political rally",
        "immigration", "deportation",
        "tariff", "tariffs", "supreme court", "white house", "legislation",
    ),
    "health": (
        "outbreak", "virus", "covid", "measles", "recall", "recalled",
        "contamination", "overdose", "hospitalized", "epidemic", "pandemic",
    ),
    "accident": (
        "crash", "crashed", "collision", "derailment", "derailed", "wreck",
        "injured", "injuries", "rescue", "rescued", "pileup",
    ),
    "adult": (
        "nude", "nudes", "nsfw", "porn", "onlyfans", "sex tape", "leaked photos",
    ),
}

# Longest term first so the reported match is the most specific one.
_PATTERNS = {
    category: re.compile(
        r"\b(?:%s)\b" % "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    )
    for category, terms in SENSITIVE_TERMS.items()
}


def _searchable(trend: dict) -> str:
    """Both the query and its linked headline -- the headline is often the
    only place the sensitive word appears (keyword 'Springfield' is harmless
    until you read the headline attached to it)."""
    return f"{trend.get('keyword') or ''} {trend.get('news_headline') or ''}".lower()


def unsafe_reason(trend: dict) -> Optional[str]:
    """Returns '<category>:<matched term>' when this trend must not be used
    as a marketing hook, or None when it is usable."""
    text = _searchable(trend)
    for category, pattern in _PATTERNS.items():
        match = pattern.search(text)
        if match:
            return f"{category}:{match.group(0)}"
    return None


def select_trends(trends: list | None, limit: int = 5) -> tuple[list, list]:
    """
    Split a state's trend items into the ones we will offer the generator and
    the ones we refused.

    Returns (usable, dropped). `usable` is ranked hottest-first and capped at
    `limit`; `dropped` records every refusal with its reason and is not
    capped, so the filter can be audited after the fact.
    """
    usable, dropped = [], []

    for trend in trends or []:
        if not isinstance(trend, dict) or not trend.get("keyword"):
            continue
        reason = unsafe_reason(trend)
        if reason:
            dropped.append({"keyword": trend["keyword"], "reason": reason})
        else:
            usable.append(trend)

    # rank 1 is hottest; items without a rank go last rather than first.
    usable.sort(key=lambda trend: (trend.get("rank") is None, trend.get("rank") or 0))
    return usable[:limit], dropped