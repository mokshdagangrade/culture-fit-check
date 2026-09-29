import os
from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import NewsDoc, NewsArticle, SourceMeta, GeoTag

BASE_URL = "https://newsdata.io/api/1/news"


class MissingAPIKey(Exception):
    pass


def fetch_news(state: dict, max_records: int = 10, timeout: int = 15) -> NewsDoc:
    api_key = os.environ.get("NEWSDATA_API_KEY")
    if not api_key:
        raise MissingAPIKey(
            "NEWSDATA_API_KEY is not set. Get a free key at newsdata.io "
            "and add it to .env."
        )

    query = state["name"]
    params = {
        "apikey": api_key,
        "q": query,
        "country": "us",
        "language": "en",
        "size": max_records,
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    raw_articles = body.get("results", []) or []
    articles = [
        NewsArticle(
            title=a.get("title", ""),
            url=a.get("link", ""),
            domain=a.get("source_id"),
            source_country=(a.get("country") or [None])[0],
            language=a.get("language"),
            seendate=a.get("pubDate"),
            tone=None,  # NewsData.io doesn't return a tone/sentiment score on the free tier
        )
        for a in raw_articles
        if a.get("title") and a.get("link")
    ]

    safe_url = resp.url.replace(api_key, "REDACTED")

    return NewsDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(
            source="newsdata.io", url=safe_url, fetched_at=datetime.now(timezone.utc),
            query=query, status="empty" if not articles else "ok",
        ),
        geo=GeoTag(scope="state", state_code=state["code"], confidence="inferred"),
        article_count=len(articles),
        articles=articles,
    )
