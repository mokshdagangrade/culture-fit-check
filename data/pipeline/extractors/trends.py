from datetime import date, datetime, timezone


from http_client import throttle_host
from schemas import TrendsDoc, TrendItem, SourceMeta, GeoTag

RSS_HOST = "trends.google.com"


def fetch_trends(state: dict, limit: int = 10) -> TrendsDoc:
    from trendspyg import download_google_trends_rss

    geo = f"US-{state['code']}"
    throttle_host(RSS_HOST)
    env = download_google_trends_rss(geo=geo, normalize=True)

    trends = [
        TrendItem(
            keyword=t["keyword"],
            rank=t.get("rank"),
            volume_min=t.get("volume_min"),
            news_headline=(t.get("news") or [{}])[0].get("headline") if t.get("news") else None,
        )
        for t in env.get("trends", [])[:limit]
    ]

    return TrendsDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(
            source="google-trends-rss",
            url=f"https://trends.google.com/trending/rss?geo={geo}",
            fetched_at=datetime.now(timezone.utc),
            status="empty" if not trends else "ok",
        ),
        geo=GeoTag(scope="state", state_code=state["code"], confidence="exact"),
        trends=trends,
    )
