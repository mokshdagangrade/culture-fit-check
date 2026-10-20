
# data/

Datasets and APIs behind Wavelength's regional signal pipeline (`pipeline/`), and the schema they produce. Setup and usage are below.

## Scope

US, all 50 states, state-level where the source allows it. State documents use `state_code` and `date`; national documents use `country_code` and `date`.

## Geography

Context falls back state → Census division → Census region → country when local data isn't available. 9 Census divisions, 4 Census regions — see `pipeline/us_states.py` for the full state→division→region mapping and `pipeline/validate.py` for the consistency check between them.

## Sources

| Signal | Source | Link | Granularity | Key needed |
|---|---|---|---|---|
| Weather | Open-Meteo | [open-meteo.com](https://open-meteo.com/) | State (capital city) | No |
| News | NewsData.io | [newsdata.io](https://newsdata.io/documentation) | State (name-keyword match) | Yes (free tier) |
| Search trends | Google "Trending now" RSS, via `trendspyg` | [Google Trends](https://trends.google.com/trending) | State | No |
| Calendar / holidays | Calendarific | [calendarific.com](https://calendarific.com/api-documentation) | State | Yes (free tier) |
| Social | Arctic Shift (Reddit archive) | [Arctic Shift](https://arctic-shift.photon-reddit.com) | State (best-effort subreddit guess) | No |
| Attention | Wikipedia Pageviews | [Wikimedia pageviews API](https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country) | National only | No |
| Sports | ESPN scoreboard (undocumented) | `site.api.espn.com` | National only, raw team/venue text | No |
| Events | Ticketmaster Discovery | [developer.ticketmaster.com](https://developer.ticketmaster.com/) | State (venue-reported) | Yes (free tier) |
| YouTube | YouTube Data API v3 — `mostPopular` | [YouTube Data API](https://developers.google.com/youtube/v3) | National only | Yes (free tier) |
| Marketing text | Hugging Face — `suehuynh/marketing-instruct-8k` | [Dataset](https://huggingface.co/datasets/suehuynh/marketing-instruct-8k) | Dataset records | No |
| Brand voice briefs | Hugging Face — `manifesta/brandvoice-marketing-briefs` | [Dataset](https://huggingface.co/datasets/manifesta/brandvoice-marketing-briefs) | Dataset records | No |

News was originally GDELT DOC 2.0 — replaced after persistent 429 rate-limiting; may revisit if NewsData.io doesn't hold up. Attention, Sports, and YouTube are fetched once per run (not once per state) and stored once in a separate national snapshot — see "Combined schema" below.

The two Hugging Face datasets provide marketing text data for downstream dataset preparation and modeling. They are separate sources and are processed independently of the regional signal extraction workflow.

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
| `state_code`, `date` | `state_code`, `date` | `country_code`, `project` | `events[]`: `league`, `event_id` |
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

### Hugging Face datasets

The marketing datasets are exported separately as JSON files by `pipeline/extractors/check_hf_datasets.py` and can then be converted to Parquet using `pipeline/notebooks/json_to_tables.ipynb`.

| Dataset | Hugging Face ID | Local JSON file |
|---|---|---|
| Marketing Instruct 8K | [`suehuynh/marketing-instruct-8k`](https://huggingface.co/datasets/suehuynh/marketing-instruct-8k) | `marketing_instruct.json` |
| Brandvoice Marketing Briefs | [`manifesta/brandvoice-marketing-briefs`](https://huggingface.co/datasets/manifesta/brandvoice-marketing-briefs) | `brandvoice_briefs.json` |

Both datasets are processed independently. Create a separate train/test split for each dataset rather than treating one dataset as training-only and the other as test-only. Keep each dataset's split membership intact during downstream processing to avoid accidentally mixing records between its training and test sets.

The exact record fields and available examples depend on the source dataset. Inspect each dataset's schema before selecting fields or applying transformations.

## Notes on trust

- **News:** NewsData.io matches on state name as a keyword, with the same caveat GDELT had (e.g. "Georgia" the country vs. the state). Free tier caps results at 10/request and has an approximately 12-hour delay.
- **Trends:** No historical window or 0–100 score (that's what the still-gated official Trends API would give) — just current rank and an approximate volume floor.
- **Social:** `subreddit` is a guessed name (state name, no spaces); `subreddit_confirmed` says whether that guess actually resolved to real posts. `geo.confidence` is `guessed` for this source.
- **Sports:** `venue_state` is raw text from ESPN, not validated against our state list, and not necessarily either team's home state (e.g. a neutral-site game). No team-to-state mapping is done here — that's left to the downstream fine-tuned LLM pipeline.
- **Events:** `venue_state` is reported directly by Ticketmaster — the most reliable state-level geo-tag in the pipeline (`geo.confidence: exact`).
- **YouTube:** No state or region filter in the API — `mostPopular` is country-level only; kept strictly national, never attributed below country.
- **Attention:** Filters out cross-language Wikipedia home/namespace pages (anything with a `:` in the title, plus known home-page titles) before returning `top_articles`.
- **Hugging Face datasets:** These are external marketing text datasets, not state-level signals. Preserve their source identity during processing. Their records should be split independently into training and test subsets; neither source is inherently reserved for only one subset.

## Combined schema

`pipeline/stitch.py` combines the six state sources. National sources and national holidays stay separate until query or training time:

```text
state_signals_daily:
  state_code, state_name, census_region, census_division,
  country_code, date, stitched_at, run_id,
  sources_present, sources_missing, source_errors,
  signals: {weather, news, trends, calendar, social, events}

national_signals_daily:
  country_code, date, run_id, windows, source_errors,
  signals: {attention, sports, youtube, calendar}
```

`run_extract.py` saves both daily JSON snapshots under `pipeline/out/`; `load_mongo.py` optionally writes them to separate collections. Matching run IDs prevent mixing collection runs. Same-day reruns replace that day's files.

The Hugging Face datasets are handled separately from these regional and national signal snapshots. Their JSON exports are converted into Parquet files for downstream analysis and modeling; they are not part of `state_signals_daily` or `national_signals_daily`.

## Setup and usage

Run from the repository root. Add API credentials to `data/pipeline/.env`:

- `NEWSDATA_API_KEY`
- `CALENDARIFIC_API_KEY`
- `TICKETMASTER_API_KEY`
- `YOUTUBE_API_KEY`
- `WIKIMEDIA_CONTACT`

Install the pipeline and notebook dependencies:

```sh
python3 -m pip install -r data/pipeline/requirements.txt -r data/pipeline/notebooks/requirements.txt
```

### Regional signal pipeline

Run a small test extraction:

```sh
python3 data/pipeline/run_extract.py --limit 1
```

Remove `--limit 1` to process all 50 states. Then run [json_to_tables.ipynb](pipeline/notebooks/json_to_tables.ipynb), followed by [data_cleaning.ipynb](pipeline/notebooks/data_cleaning.ipynb). Both default to the latest saved day; use `RUN_DATE` or `SIGNAL_RUN_DATE` to select another.

Run the pipeline tests:

```sh
python3 -m unittest discover -s data/pipeline -p 'test*.py' -v
```

### Hugging Face marketing datasets

The Hugging Face export script downloads the two marketing datasets and saves their JSON exports under `data/pipeline/out/`.

Run the exporter from the repository root:

```sh
python3 data/pipeline/extractors/check_hf_datasets.py
```

Expected JSON files:

```text
data/pipeline/out/
  marketing_instruct.json
  brandvoice_briefs.json
```

Next, run `data/pipeline/notebooks/json_to_tables.ipynb`. The notebook reads the JSON exports and converts each dataset into a separate Parquet file. The intended output location is the same date-partitioned folder used for the existing tables:

```text
data/pipeline/out/tables/date=YYYY-MM-DD/
  marketing_instruct.parquet
  brandvoice_briefs.parquet
```

Confirm the actual output paths and filenames against the exporter and notebook configuration if these differ in your local setup. The date partition used by the notebook should be consistent with the existing table conversion run.

For downstream modeling, create separate train/test splits for each dataset. Do not use one dataset as a substitute for the other dataset's test set.

## Age settings and calendar cache

Edit `pipeline/signal_windows.json`: each API has `lookback_days` and `lookahead_days`. Pass another complete file with `--windows /path/to/windows.json`, and use the same file through `WINDOWS_PATH` or `SIGNAL_WINDOWS_PATH` in cleaning. Age is measured against the saved reference time. Trends and YouTube freshness uses collection time.

Calendarific fetches the US once per needed year and caches it for 30 days, conserving its 500-request monthly allowance. Use `--calendar-cache-days N` or `--refresh-calendar` to change refresh behaviour. State holiday `observance_note` preserves partial, optional and community-specific observance.

## Tables and quality checks

Converted regional tables are saved to `pipeline/out/tables/date=YYYY-MM-DD/`; cleaned tables and `signal_candidate` go to `pipeline/out/clean/date=YYYY-MM-DD/`. National rows have null state codes. Each folder includes `quality_report.json`.

The Hugging Face conversion adds one Parquet file per dataset to the tables output directory. These files contain the respective source dataset's records and are separate from the regional signal tables. Verify row counts and column names after conversion.

Raw rows are retained. Cleaning removes news and Reddit repeats only when state, collection date, cleaned URL and normalized title all match; the first copy stays. Textless candidates are excluded. Other duplicates, noise, age and availability are flagged. Missing reference timestamps block saving; unknown publication dates remain unknown, and upcoming events are allowed.

Larger age windows cannot recover uncollected history. Ticketmaster reports when its 50-item cap leaves more listings unfetched. Sports collects NFL, NCAA football, NBA, WNBA, NCAA men's/women's basketball, MLB, NHL and MLS from the reference date through four days ahead by default (no past dates). Requests use one day at a time: 45 requests per run with the default nine leagues and five dates. Edit `LEAGUES` in `pipeline/extractors/sports.py` to change coverage; age windows remain configurable. Each game retains its league and event ID; league failures are reported without discarding other leagues. Empty results can reflect an off-season. Verify state-level Trends coverage.

Collect across dates, and keep repeated content out of both training and evaluation sets. Product relevance selection and marketing responses remain later work.