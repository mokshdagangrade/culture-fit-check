# data/

Datasets and APIs behind Wavelength's regional signal pipeline (`pipeline/`), and the schema they produce. For setup and how to run it, see `pipeline/README.md`.

## Scope

US, all 50 states, state-level where the source allows it. Every document is keyed by `state_code` and `date`.

## Geography

Context falls back state → Census division → Census region → country when local data isn't available. 9 Census divisions, 4 Census regions — see `pipeline/us_states.py` for the full state→division→region mapping and `pipeline/validate.py` for the consistency check between them.

## Sources

| Signal | Source | Link | Granularity | Key needed |
|---|---|---|---|---|
| Weather | Open-Meteo | [open-meteo.com](https://open-meteo.com/) | State (capital city) | No |
| News | NewsData.io | [newsdata.io](https://newsdata.io/documentation) | State (name-keyword match) | Yes (free tier) |
| Search trends | Google "Trending now" RSS, via `trendspyg` | [trends.google.com/trending](https://trends.google.com/trending) | State | No |
| Calendar / holidays | Calendarific | [calendarific.com](https://calendarific.com/api-documentation) | State | Yes (free tier) |
| Social | Arctic Shift (Reddit archive) | [arctic-shift.photon-reddit.com](https://arctic-shift.photon-reddit.com) | State (best-effort subreddit guess) | No |
| Attention | Wikipedia Pageviews | [wikimedia.org pageviews API](https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country) | National only | No |
| Sports | ESPN scoreboard (undocumented) | `site.api.espn.com` | National only, raw team/venue text | No |
| Events | Ticketmaster Discovery | [developer.ticketmaster.com](https://developer.ticketmaster.com/) | State (venue-reported) | Yes (free tier) |
| YouTube | YouTube Data API v3 — `mostPopular` | [developers.google.com/youtube](https://developers.google.com/youtube/v3) | National only | Yes (free tier) |

News was originally GDELT DOC 2.0 — replaced after persistent 429 rate-limiting; may revisit if NewsData.io doesn't hold up. Attention, Sports, and YouTube are fetched once per run (not once per state) and the same document is attached to every state — see "Combined schema" below.

## Per-source schema

Every raw document carries a shared `meta` block: `source`, `url`, `fetched_at`, `data_time` (not yet populated by any extractor), `query`, `status` (`ok`/`empty`/`error`), `error`.

Every raw document also carries a `geo` block: `scope` (`national`/`region`/`division`/`state`/`city`), `state_code`, `census_region`, `census_division`, `confidence` (`exact`/`inferred`/`guessed`/`unreliable`).

| Weather | News | Trends |
|---|---|---|
| `state_code`, `date` | `state_code`, `date` | `state_code`, `date` |
| `temperature_c` | `article_count` | `trends[]`: |
| `temperature_max_c` / `min_c` | `articles[]`: | &nbsp;&nbsp;`keyword`, `rank` |
| `precipitation_mm` | &nbsp;&nbsp;`title`, `url`, `domain` | &nbsp;&nbsp;`volume_min` |
| `weather_code`, `condition` | &nbsp;&nbsp;`source_country`, `language` | &nbsp;&nbsp;`news_headline` |
| | &nbsp;&nbsp;`seendate`, `tone` | |

| Calendar | Social | Attention (national) | Sports (national) |
|---|---|---|---|
| `state_code`, `date` | `state_code`, `date` | `country_code`, `project` | `league` |
| `holidays_today[]` | `subreddit` | `top_articles[]` | `events[]`: |
| `holidays_this_month[]`: | `subreddit_confirmed` | | &nbsp;&nbsp;`home_team`, `away_team` |
| &nbsp;&nbsp;`name`, `date`, `type` | `posts[]`: | | &nbsp;&nbsp;`venue_name`, `venue_city`, `venue_state` |
| &nbsp;&nbsp;`state_specific` | &nbsp;&nbsp;`title`, `subreddit`, `score` | | &nbsp;&nbsp;`start_time`, `status` |
| | &nbsp;&nbsp;`url`, `created_utc` | | |

| Events (state) | YouTube (national) |
|---|---|
| `state_code`, `date` | `country_code`, `date` |
| `events[]`: | `videos[]`: |
| &nbsp;&nbsp;`name`, `url`, `start_date` | &nbsp;&nbsp;`title`, `channel_title`, `video_id` |
| &nbsp;&nbsp;`venue_name`, `venue_city`, `venue_state` | &nbsp;&nbsp;`category_id`, `view_count`, `published_at` |
| &nbsp;&nbsp;`classification`, `genre` | |
| &nbsp;&nbsp;`price_min`, `price_max` | |

Notes on trust:
- **News** (NewsData.io) matches on state name as a keyword, same caveat GDELT had (e.g. "Georgia" the country vs. the state). Free tier caps results at 10/request and has a ~12-hour delay.
- **Trends** has no historical window or 0-100 score (that's what the still-gated official Trends API would give) — just current rank and an approximate volume floor.
- **Social**'s `subreddit` is a guessed name (state name, no spaces); `subreddit_confirmed` says whether that guess actually resolved to real posts. `geo.confidence` is `guessed` for this source.
- **Sports**' `venue_state` is raw text from ESPN, not validated against our state list, and not necessarily either team's home state (e.g. a neutral-site game). No team→state mapping is done here — that's left to the downstream fine-tuned LLM pipeline.
- **Events**' `venue_state` is reported directly by Ticketmaster — the most reliable state-level geo-tag in the pipeline (`geo.confidence: exact`).
- **YouTube** has no state or region filter in the API — `mostPopular` is country-level only; kept strictly national, never attributed below country.
- **Attention** filters out cross-language Wikipedia home/namespace pages (anything with a `:` in the title, plus known home-page titles) before returning `top_articles`.

## Combined schema

Two Mongo-shaped layers:

**Raw layer** — one collection per source above, one document per (state, source, day), exactly what the API returned. Append-only audit trail.

**Stitched layer** — `state_signals_daily`, one document per (state, day), joining that day's raw signals:

```
{
state_code, state_name, census_region, census_division,
date, stitched_at,
sources_present: [...], # which signals actually came through
sources_missing: [...], # which didn't (see meta.error upstream, printed to console)
signals: {
weather, news, trends, calendar, social, events, # per-state
attention, sports, youtube # national, same doc reused for every state
}
}
```

This is the document a ranker or generator would query. `pipeline/run_extract.py` builds it; `pipeline/load_mongo.py` inserts it.