from datetime import date, datetime, timezone

from http_client import polite_get
from schemas import SocialDoc, RedditPost, SourceMeta, GeoTag

BASE_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"


def fetch_subreddit_posts(state: dict, limit: int = 20, timeout: int = 15) -> SocialDoc:
    subreddit_guess = state["name"].replace(" ", "")
    params = {"subreddit": subreddit_guess, "limit": limit, "sort": "desc"}

    resp = polite_get(BASE_URL, params=params, timeout=timeout)

    if resp.status_code == 404:
        return SocialDoc(
            state_code=state["code"],
            date=date.today(),
            meta=SourceMeta(
                source="arctic-shift", url=resp.url, fetched_at=datetime.now(timezone.utc),
                status="error", error=f"r/{subreddit_guess} not found",
            ),
            subreddit=subreddit_guess,
            subreddit_confirmed=False,
            posts=[],
        )
    resp.raise_for_status()

    rows = resp.json().get("data", [])
    posts = [
        RedditPost(
            title=r.get("title", ""),
            subreddit=r.get("subreddit", subreddit_guess),
            score=r.get("score"),
            url=r.get("url"),
            created_utc=r.get("created_utc"),
        )
        for r in rows
        if r.get("title")
    ]

    return SocialDoc(
        state_code=state["code"],
        date=date.today(),
        meta=SourceMeta(
            source="arctic-shift", url=resp.url, fetched_at=datetime.now(timezone.utc),
            status="empty" if not posts else "ok",
        ),
        geo=GeoTag(scope="state", state_code=state["code"], confidence="guessed"), #guessed because we are getting geolocation based on subreddit
        subreddit=subreddit_guess,
        subreddit_confirmed=bool(posts),   #got real rows back, so the subreddit is at least active
        posts=posts,
    )
