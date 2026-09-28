# data/

Datasets and APIs behind Wavelength's regional signal pipeline (`pipeline/`), and the schema they produce. For setup and how to run it, see `pipeline/README.md`.

## Scope

US, all 50 states, state-level where the source allows it. Every document is keyed by `state_code` and `date`.

## Sources

| Signal | Source | Link | Granularity | Key needed |
|---|---|---|---|---|
| Weather | Open-Meteo | [open-meteo.com](https://open-meteo.com/) | State (capital city) | No |
| News | GDELT DOC 2.0 | [api.gdeltproject.org](https://api.gdeltproject.org/api/v2/doc/doc) | State (name-keyword match) | No |
| Search trends | Google "Trending now" RSS, via `trendspyg` | [trends.google.com/trending](https://trends.google.com/trending) | State | No |
| Calendar / holidays | Calendarific | [calendarific.com](https://calendarific.com/api-documentation) | State | Yes (free tier) |
| Social | Arctic Shift (Reddit archive) | [arctic-shift.photon-reddit.com](https://arctic-shift.photon-reddit.com) | State (best-effort subreddit guess) | No |
| Attention | Wikipedia Pageviews | [wikimedia.org pageviews API](https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country) | National only | No |
| Sports | ESPN scoreboard (undocumented) | `site.api.espn.com` | National only, raw team/venue text | No |

Attention and Sports are fetched once per run (not once per state) and the same document is attached to every state — see "Combined schema" below.

## Per-source schema

Every raw document carries a shared `meta` block: `source`, `url`, `fetched_at`, `status` (`ok`/`empty`/`error`), `error`.

| Weather | News | Trends |
|---|---|---|
| `state_code`, `date` | `state_code`, `date` | `state_code`, `date` |
| `temperature_c` | `query` | `trends[]`: |
| `temperature_max_c` / `min_c` | `article_count` | &nbsp;&nbsp;`keyword`, `rank` |
| `precipitation_mm` | `articles[]`: | &nbsp;&nbsp;`volume_min` |
| `weather_code`, `condition` | &nbsp;&nbsp;`title`, `url`, `domain` | &nbsp;&nbsp;`news_headline` |
| | &nbsp;&nbsp;`source_country`, `language` | |
| | &nbsp;&nbsp;`seendate`, `tone` | |

| Calendar | Social | Attention (national) | Sports (national) |
|---|---|---|---|
| `state_code`, `date` | `state_code`, `date` | `country_code`, `project` | `league` |
| `holidays_today[]` | `subreddit` | `top_articles[]` | `events[]`: |
| `holidays_this_month[]`: | `subreddit_confirmed` | | &nbsp;&nbsp;`home_team`, `away_team` |
| &nbsp;&nbsp;`name`, `date`, `type` | `posts[]`: | | &nbsp;&nbsp;`venue_name`, `venue_city`, `venue_state` |
| &nbsp;&nbsp;`state_specific` | &nbsp;&nbsp;`title`, `subreddit`, `score` | | &nbsp;&nbsp;`start_time`, `status` |
| | &nbsp;&nbsp;`url`, `created_utc` | | |

Notes on trust:
- **Trends** has no historical window or 0-100 score (that's what the still-gated official Trends API would give) — just current rank and an approximate volume floor.
- **Social**'s `subreddit` is a guessed name (state name, no spaces); `subreddit_confirmed` says whether that guess actually resolved to real posts.
- **Sports**' `venue_state` is raw text from ESPN, not validated against our state list, and not necessarily either team's home state (e.g. a neutral-site game). No team→state mapping is done here — that's left to the downstream fine-tuned LLM pipeline.

## Combined schema

Two Mongo-shaped layers:

**Raw layer** — one collection per source above, one document per (state, source, day), exactly what the API returned. Append-only audit trail.

**Stitched layer** — `state_signals_daily`, one document per (state, day), joining that day's raw signals:

```
{
  state_code, state_name, region,
  date, stitched_at,
  sources_present: [...],   # which signals actually came through
  sources_missing: [...],   # which didn't, and why (see meta.error upstream)
  signals: {
    weather, news, trends, calendar, social,   # per-state
    attention, sports                          # national, same doc reused for every state
  }
}
```

This is the document a ranker or generator would query. `pipeline/run_extract.py` builds it; `pipeline/load_mongo.py` inserts it.