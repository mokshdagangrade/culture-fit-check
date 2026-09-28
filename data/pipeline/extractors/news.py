from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import NewsDoc, NewsArticle, SourceMeta

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT asks that automated clients throttle to roughly 1 request
# per 5 seconds -- enforced in http_client.py (6s gap for this host).


def fetch_news(state: dict, max_records: int = 25, timeout: int = 15) -> NewsDoc:
    """
    state: one entry from us_states.US_STATES (needs code, name).
    Returns a validated NewsDoc. Raises requests.RequestException or http_client.RateLimited
    on network failure.
    """
    query = f'"{state["name"]}" sourcecountry:US'
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records,
        "sort": "datedesc",
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    raw_articles = body.get("articles", [])
    articles = [
        NewsArticle(
            title=a.get("title", ""),
            url=a.get("url", ""),
            domain=a.get("domain"),
            source_country=a.get("sourcecountry"),
            language=a.get("language"),
            seendate=a.get("seendate"),
            tone=a.get("tone"),
        )
        for a in raw_articles
        if a.get("title") and a.get("url")   # drop malformed entries, don't silently keep them
    ]

    return NewsDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(
            source="gdelt",
            url=resp.url,
            fetched_at=datetime.now(timezone.utc),
            status="empty" if not articles else "ok",
        ),
        query=query,
        article_count=len(articles),
        articles=articles,
    )
