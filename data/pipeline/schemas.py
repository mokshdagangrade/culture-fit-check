"""
Schema for the two Mongo layers.

RAW layer (one collection per source): stores what an API returned,
lightly parsed, one document per (state, source, fetch). Append-only,
never overwritten. This is the audit trail.

    raw_weather      <- WeatherDoc
    raw_news         <- NewsDoc
    raw_trends       <- TrendsDoc   (stub for now, see extractors/trends.py)

STITCHED layer (one collection): one document per (state, date),
joining that day's raw signals by state_code. This is what a
downstream ranker/generator would read.

    state_signals_daily  <- StitchedDoc

Everything here is a pydantic model so the same class both validates
data before insert and documents the schema in one place.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from us_states import STATE_CODES


def _validate_state_code(v: str) -> str:
    if v not in STATE_CODES:
        raise ValueError(f"'{v}' is not a valid two-letter US state code")
    return v


class SourceMeta(BaseModel):
    """Recorded on every raw document, regardless of source."""
    source: str                    # e.g. "open-meteo", "gdelt"
    url: str                       # exact request URL (helps reproduce / debug)
    fetched_at: datetime
    status: str = "ok"             # "ok" | "error" | "empty"
    error: Optional[str] = None


class WeatherDoc(BaseModel):
    state_code: str
    date: date
    meta: SourceMeta
    temperature_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    temperature_min_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    weather_code: Optional[int] = None       # Open-Meteo WMO code
    condition: Optional[str] = None          # human-readable, derived from weather_code

    _v_state = field_validator("state_code")(_validate_state_code)


class NewsArticle(BaseModel):
    title: str
    url: str
    domain: Optional[str] = None
    source_country: Optional[str] = None
    language: Optional[str] = None
    seendate: Optional[str] = None
    tone: Optional[float] = None             # GDELT tone score, raw and unfiltered for now


class NewsDoc(BaseModel):
    state_code: str
    date: date
    meta: SourceMeta
    query: str                                # the keyword query actually sent (state name)
    article_count: int = 0
    articles: list[NewsArticle] = Field(default_factory=list)

    _v_state = field_validator("state_code")(_validate_state_code)


class TrendItem(BaseModel):
    keyword: str
    rank: Optional[int] = None
    volume_min: Optional[int] = None          # Google's floor estimate, e.g. "500K+" -> 500000
    news_headline: Optional[str] = None       # first linked news headline, if any


class TrendsDoc(BaseModel):
    """
    Google's public "Trending now" RSS feed (via the trendspyg
    library), not the gated Trends API. It has no historical window
    and no 0-100 interest score -- just what's trending right now,
    ranked, with an approximate volume floor. See extractors/trends.py.
    """
    state_code: str
    date: date
    meta: SourceMeta
    trends: list[TrendItem] = Field(default_factory=list)

    _v_state = field_validator("state_code")(_validate_state_code)


class AttentionDoc(BaseModel):
    """
    Wikipedia Pageviews' 'top articles' endpoint is per project
    (language edition) or per country, not per US state. Same
    same national/shared treatment applies here.
    """
    scope: str = "national"
    country_code: str = "US"
    project: str = "en.wikipedia"
    date: date
    meta: SourceMeta
    top_articles: list[str] = Field(default_factory=list)


class Holiday(BaseModel):
    name: str
    date: str
    type: Optional[str] = None
    state_specific: bool = False


class CalendarDoc(BaseModel):
    state_code: str
    date: date
    meta: SourceMeta
    holidays_today: list[Holiday] = Field(default_factory=list)
    holidays_this_month: list[Holiday] = Field(default_factory=list)

    _v_state = field_validator("state_code")(_validate_state_code)


class RedditPost(BaseModel):
    title: str
    subreddit: str
    score: Optional[int] = None
    url: Optional[str] = None
    created_utc: Optional[float] = None


class SocialDoc(BaseModel):
    """
    Reddit has no official state->subreddit mapping. `subreddit` is
    a best-effort guess (state name, spaces removed, e.g. "Texas",
    "NewYork") and `subreddit_confirmed` records whether we actually
    verified the subreddit exists and is active before trusting it.
    """
    state_code: str
    date: date
    meta: SourceMeta
    subreddit: str
    subreddit_confirmed: bool = False
    posts: list[RedditPost] = Field(default_factory=list)

    _v_state = field_validator("state_code")(_validate_state_code)


class SportsEvent(BaseModel):
    """
    Left deliberately raw and unresolved: team names and venue text
    exactly as ESPN reports them, no state assigned here. A
    fine-tuned model downstream is expected to map these to a state
    (e.g. "Georgia Bulldogs" + venue "Athens, GA" -> "GA"), so
    normalizing it here would just be duplicate, lower-quality work.
    """
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    venue_state: Optional[str] = None   # as ESPN reports it, if present -- not validated against STATE_CODES
    start_time: Optional[str] = None
    status: Optional[str] = None


class SportsDoc(BaseModel):
    """
    National scope, same treatment as AttentionDoc: ESPN's scoreboard
    is fetched once per run (not once per state) and the same
    SportsDoc is attached to every state's StitchedDoc. No
    team-to-state mapping is done here -- see the SportsEvent
    docstring.
    """
    scope: str = "national"
    league: str = "college-football"
    date: date
    meta: SourceMeta
    events: list[SportsEvent] = Field(default_factory=list)


class StitchedSignals(BaseModel):
    """The joined payload inside a StitchedDoc."""
    weather: Optional[WeatherDoc] = None
    news: Optional[NewsDoc] = None
    trends: Optional[TrendsDoc] = None
    attention: Optional[AttentionDoc] = None
    calendar: Optional[CalendarDoc] = None
    social: Optional[SocialDoc] = None
    sports: Optional[SportsDoc] = None


class StitchedDoc(BaseModel):
    """
    One per (state_code, date). This is the document a ranker or
    generator would actually query against.
    """
    state_code: str
    state_name: str
    region: str
    date: date
    stitched_at: datetime
    sources_present: list[str]                 # e.g. ["weather", "news", "calendar"]
    sources_missing: list[str]                 # e.g. ["trends", "sports"]
    signals: StitchedSignals

    _v_state = field_validator("state_code")(_validate_state_code)
