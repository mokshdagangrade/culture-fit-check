# data/

Datasets, APIs, and annotation guidelines for Wavelength.

## Scope

Two settings, compared against each other:

| Setting | Coverage | Language | Role in the evaluation |
|---|---|---|---|
| **US** | State-level | English | Control condition (dialect and register variation, no code-mixing) |
| **India** | State / city-level | Hindi-English code-mixed ("Hinglish") | Stress test (code-mixing, festival and language diversity) |

Launch regions (3-4 US states, 3-4 Indian cities/states) are **not decided yet**. Weather lookups currently cover six placeholder cities in `src/backend/trend_retrieval.py`.

## Regional granularity

Not every source can target a state or city. This decides which signals can be compared across regions.

| Signal | Finest region available |
|---|---|
| Search (Google Trends) | State |
| News (GDELT, NewsAPI) | Country. State or city targeting needs keyword filtering (e.g. searching for a city name). |
| Video (YouTube) | Country |
| Attention (Wikipedia Pageviews) | Country, or language edition |
| Attention (Reddit) | Per subreddit |
| Weather | City |
| Festivals and holidays | State |

## Planned structure

```
data/
├── us/           # US signals and examples (state-level, English)
├── india/        # India signals and examples (state/city-level, Hinglish)
├── annotations/  # Annotation guidelines and human ratings, kept separate per region
└── README.md
```

Small files the running app reads at runtime (for example a festival list) can live next to the backend code instead.

---

## Sources

| Signal | Source | Region | Link | Notes |
|---|---|---|---|---|
| Search | Google Trends API (alpha) | US + India | [Apply / docs](https://developers.google.com/search/apis/trends) | Application required (gated alpha). State-level via ISO 3166-2, about 5 years of data, roughly 2 days behind. Unclear whether it lists trending topics or only measures terms we supply. Unofficial fallback: [pytrends](https://github.com/GeneralMills/pytrends) (archived Apr 2025, partly broken). |
| News | GDELT DOC 2.0 | US + India | [API endpoint](https://api.gdeltproject.org/api/v2/doc/doc) | No key. 65 languages, last 3 months only, with tone and theme filters. Country-level. Returns titles and URLs, not full text. A community guide reports a limit of 1 request per 5 seconds. |
| News | NewsAPI | US + India | [Pricing / docs](https://newsapi.org/pricing) | Free tier is for development only: 100 requests/day, 24-hour article delay. Production plans start at $449/month. Fallback only. |
| Video | YouTube Data API v3 | US + India | [Docs](https://developers.google.com/youtube/v3/guides/implementation/videos) | Free API key. Use `videos.list` with `chart=mostPopular` and `regionCode`. 10,000 quota units/day (a list call costs 1, a search costs 100). Country-level only. |
| Attention | Wikipedia Pageviews API | US + India | [Docs](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html) | No key, but a descriptive User-Agent is required. Top 1,000 pages per day, per language edition or country. Filter out non-topic pages like the main page. |
| Attention | Reddit Data API | US (+ India) | [Register app](https://www.reddit.com/prefs/apps) | Free tier is non-commercial only, 100 queries/minute. New access reportedly needs manual approval (verify). |
| Weather | Open-Meteo | US + India | [Docs](https://open-meteo.com/) | **Already used in the repo.** No key. Free for non-commercial use (under 10,000 calls/day). Data is CC BY 4.0, so attribution is required. |
| Weather | NWS API | US | [Docs](https://www.weather.gov/documentation/services-web-api) | No key, but a User-Agent header with contact info is required. Public-domain data, includes severe-weather alerts. |
| Weather | OpenWeather One Call 3.0 | US + India | [Docs](https://openweathermap.org/api/one-call-3) | API key. 1,000 calls/day free on the "One Call by Call" plan. Data under ODbL, API under CC BY-SA 4.0. Backup only. |
| Weather | IMD APIs | India | [API portal](https://api.imd.gov.in/) | Needs registration and IP whitelisting. Attribution required. Likely slow to set up, so use Open-Meteo for India in v1. |
| Calendar | Calendarific | US + India | [Docs](https://calendarific.com/api-documentation) | API key. Free plan: 500 calls/month, attribution required. Check how well it covers regional festivals (Onam, Pongal, Durga Puja). |
| Calendar | Team festival list | India | `src/backend/data/festivals.json` (to be created) | Hand-curated, state-specific. Store month ranges, since festival dates shift with the lunar calendar. |
| Sports | ESPN hidden API | US | [Community docs](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b) | Undocumented and unofficial, so it can break, and we found no reuse terms. Prototype only. |
| Sports | Cricsheet | India | [Site](https://cricsheet.org) | Free open ball-by-ball data (JSON, YAML, CSV). Historical only, with no upcoming fixtures. Credit Cricsheet and confirm its terms. |
| Language | Harvard Dialect Survey | US | [Background article](https://news.harvard.edu/gazette/story/2002/12/standing-on-line-at-the-bubbler-with-a-hoagie-in-my-hand) | 122 questions, 30,000+ respondents (2002-03), results by state. Old data. No direct data link found and reuse terms unknown. Related: [NYT dialect quiz](https://www.nytimes.com/interactive/2014/upshot/dialect-quiz-map.html). |
| Language | TwitterAAE (Blodgett et al.) | US | [Project page](https://slanglab.cs.umass.edu/TwitterAAE) | Research use only. Covers African-American English (demographic dialect), not state-level regional slang. Possible use: checking for bias. |
| Language | L3Cube-HingCorpus / HingBERT | India | [GitHub](https://github.com/l3cube-pune/code-mixed-nlp) | 52.93M Hinglish sentences scraped from Twitter. Models are CC BY 4.0 on [Hugging Face](https://huggingface.co/l3cube-pune/hing-bert), including HingBERT-LID for language ID. Confirm the corpus license. |
| Language | SemEval-2020 Task 9 (SentiMix) | India | [Task page](https://ritual-uh.github.io/sentimix2020/) | 20,000 labeled Hinglish tweets (positive / negative / neutral). Data via [CodaLab](https://competitions.codalab.org/competitions/20654) with registration. Dataset terms unconfirmed. |
| Language | COMI-LINGUA | India | [Paper](https://arxiv.org/abs/2503.21670) | Human-annotated Hinglish benchmark for evaluation. License not checked. GLUECoS and LinCE are similar code-mixed benchmarks. |
| Copy examples | Meta Content Library | US + India | [Info](https://transparency.fb.com) | Public Facebook and Instagram posts, but only for vetted academic and nonprofit researchers via ICPSR. Approval reportedly takes 2-6 weeks, so likely too slow. Alternative: manually collect 20-50 public brand posts per region (check platform terms). |

