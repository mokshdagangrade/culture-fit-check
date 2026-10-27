"""
Stage 2 of signal retrieval: pick the few signals worth writing about.

Given ~40 safe candidates for a state and one brand brief, decide which two
or three a marketer would actually use. One batched LLM call, scored 0-10
with a one-line reason each.

Why a model and not a vector search: the candidates are 40-character titles
of mostly proper nouns ("first frost austin", "Yom Kippur", "Dinosaur World
Live!") and the brief is abstract. There is nothing for lexical overlap to
find -- on the real Texas snapshot the best TF-IDF match to a coffee brief
scored 0.037 and was matching the word "friends" in band names. "Would this
make a good hook for this brand" is a judgement, so a model makes it.

This call is also the label factory. Every selection is recorded with its
score and reason; once a few hundred have been through human review, the
same decision can be learned by something far cheaper and this call drops
out of the request path.

Failure here is never fatal: abstain from selecting hooks when ranking is
unavailable. Generation can still use the brand and brief.
"""

import json
import logging
import math
import re

import llm

logger = logging.getLogger(__name__)

RANKER_SYSTEM = (
    "You select local signals that a marketing team could build copy around. "
    "You are strict: most signals are irrelevant to any given brand, and "
    "saying so is the correct answer. You reply with JSON only."
)

MAX_SELECTED = 3
# Below this the signal is a worse hook than no hook at all.
SCORE_FLOOR = 5


def build_ranking_prompt(brief: str, company: dict, state: str, pool: list) -> str:
    lines = []
    for i, signal in enumerate(pool):
        event_date = f" [event date: {signal['event_date']}]" if signal.get("event_date") else ""
        context = f" -- {signal['context']}" if signal.get("context") else ""
        scope = " [national]" if signal.get("is_national") else ""
        if signal.get("geo_confidence") == "guessed":
            scope += " [guessed geography, anecdotal]"
        lines.append(f"{i}. ({signal['source']}{scope}) {signal['text']}{event_date}{context}")

    return f"""Brand: {company.get("name", "Unknown")} ({company.get("industry", "unknown industry")})
Brand voice: {company.get("brand_voice", "not provided")}
Market: {state}
Campaign brief: {brief}

Candidate local signals happening in {state} right now:
{chr(10).join(lines)}

Score how useful each signal is as a hook for THIS campaign, 0-10:
- 8-10: a marketer would obviously use it; it connects to the product or the moment
- 4-7: plausible but a stretch
- 0-3: irrelevant, or the connection would feel forced or tasteless

Most signals score low. Do not inflate scores to fill a quota.

Reply with JSON only, no prose, no code fence:
[{{"id": <number>, "score": <0-10>, "why": "<at most 12 words>"}}]
Include only signals scoring {SCORE_FLOOR} or above. An empty array [] is a valid answer."""


def parse_ranking(raw: str, pool: list) -> list:
    """Pull the JSON array out of the reply, tolerating fences and stray prose."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("["):
        match = re.search(r"\[.*\]", text, re.S)
        if not match:
            raise ValueError("no JSON array in ranker reply")
        text = match.group(0)

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("ranker response must be an array")
    scored, seen = [], set()
    for row in parsed:
        if not isinstance(row, dict):
            continue
        try:
            index = int(row["id"])
            score = float(row["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if (not 0 <= index < len(pool) or not math.isfinite(score)
                or not SCORE_FLOOR <= score <= 10 or index in seen):
            continue
        seen.add(index)
        scored.append({**pool[index],
                       "score": score,
                       "why": str(row.get("why", ""))[:120]})

    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:MAX_SELECTED]


def rank_signals(brief: str, company: dict, state: str, pool: list) -> tuple[list, str]:
    """
    Returns (selected, method). `method` is "llm" when the model chose,
    "fallback" when it could not and selection abstained, and names the
    failure in the audit trail either way.
    """
    if not pool:
        return [], "empty-pool"
    if not llm.is_configured():
        return [], "fallback:no-llm"

    try:
        raw = llm.call_llm(
            build_ranking_prompt(brief, company, state, pool),
            system=RANKER_SYSTEM,
            temperature=0,
            max_tokens=600,
        )
    except llm.LLMError as exc:
        logger.warning("Signal ranker call failed: %s", exc)
        return [], "fallback:llm-error"

    try:
        return parse_ranking(raw, pool), "llm"
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Signal ranker returned unparseable JSON: %s", exc)
        return [], "fallback:bad-json"