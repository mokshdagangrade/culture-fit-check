import os
from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import YoutubeDoc, YoutubeVideoItem, SourceMeta

BASE_URL = "https://www.googleapis.com/youtube/v3/videos"


class MissingAPIKey(Exception):
    pass


def fetch_trending(country_code: str = "US", max_results: int = 25, timeout: int = 10) -> YoutubeDoc:
    """
    YouTube's mostPopular chart is filtered by regionCode (country only) --
    there is no state or region parameter. Always national scope; see
    schemas.YoutubeDoc for why per-video geolocation search was rejected
    (sparse, opt-in only, unreliable coverage).
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise MissingAPIKey(
            "YOUTUBE_API_KEY is not set. Create one in Google Cloud Console "
            "(enable YouTube Data API v3) and add it to .env."
        )

    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": country_code,
        "maxResults": max_results,
        "key": api_key,
    }
    resp = polite_get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    raw_videos = body.get("items", [])
    videos = [
        YoutubeVideoItem(
            title=v.get("snippet", {}).get("title", ""),
            channel_title=v.get("snippet", {}).get("channelTitle"),
            video_id=v.get("id", ""),
            category_id=v.get("snippet", {}).get("categoryId"),
            view_count=int(v["statistics"]["viewCount"]) if v.get("statistics", {}).get("viewCount") else None,
            published_at=v.get("snippet", {}).get("publishedAt"),
        )
        for v in raw_videos
        if v.get("id")
    ]

    safe_url = resp.url.replace(api_key, "REDACTED")

    return YoutubeDoc(
        country_code=country_code,
        date=date.today(),
        meta=SourceMeta(
            source="youtube", url=safe_url, fetched_at=datetime.now(timezone.utc),
            status="empty" if not videos else "ok",
        ),
        videos=videos,
    )