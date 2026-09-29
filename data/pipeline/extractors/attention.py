import os
from datetime import date, datetime, timedelta, timezone

from http_client import polite_get
from schemas import AttentionDoc, SourceMeta

BASE_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country"
MAX_DAYS_BACK = 5

NOISE_TITLES = {"Special:Search", "Special:CentralAutoLogin/checkForCookies"}

# Any language's home page / portal, e.g. "Main_Page", "Wikipedia:Portada",
# "メインページ", "Wikipédia:Accueil_principal" -- these show up regardless of
# country because pageviews aren't filtered by article language, only by
# who's viewing.
NOISE_SUFFIXES = ("Main_Page", "メインページ", "首页", "Hauptseite")


def _is_noise(title: str) -> bool:
    if title in NOISE_TITLES:
        return True
    if ":" in title:  # catches "Wikipedia:", "Wikipédia:", "特別:" etc. -- namespace pages, not articles
        return True
    if title.endswith(NOISE_SUFFIXES):
        return True
    return False

class NoDataAvailable(Exception):
    pass


def fetch_top_attention(country_code: str = "US", limit: int = 20, timeout: int = 10) -> AttentionDoc:
    contact = os.environ.get("WIKIMEDIA_CONTACT")
    if not contact:
        raise RuntimeError(
            "WIKIMEDIA_CONTACT is not set. Wikimedia requires a descriptive "
            "User-Agent with contact info -- add e.g. your email to .env."
        )
    headers = {"User-Agent": f"wavelength-pipeline/0.1 ({contact})"}

    last_404 = None
    for days_back in range(1, MAX_DAYS_BACK + 1):
        target_day = datetime.now(timezone.utc).date() - timedelta(days=days_back)
        url = f"{BASE_URL}/{country_code}/all-access/{target_day.strftime('%Y/%m/%d')}"

        resp = polite_get(url, headers=headers, timeout=timeout)
        if resp.status_code == 404:
            last_404 = target_day
            continue
        resp.raise_for_status()
        body = resp.json()

        articles = body.get("items", [{}])[0].get("articles", [])
        top = [a["article"] for a in articles if not _is_noise(a.get("article", ""))][:limit]

        return AttentionDoc(
            country_code=country_code,
            date=date.today(),
            meta=SourceMeta(
                source="wikipedia-pageviews",
                url=url,
                fetched_at=datetime.now(timezone.utc),
                status="empty" if not top else "ok",
                error=(f"used {target_day.isoformat()} data, most recent {days_back - 1} "
                       f"day(s) not published yet") if days_back > 1 else None,
            ),
            top_articles=top,
        )

    raise NoDataAvailable(
        f"Wikimedia had no top-per-country data for {country_code} for the last "
        f"{MAX_DAYS_BACK} days (last tried {last_404})."
    )
