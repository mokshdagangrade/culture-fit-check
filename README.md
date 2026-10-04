# culture-fit-check
Detects cultural/localization mismatches in marketing copy by grounding judgments in real regional trend and reference data, not just LLM guesses.

## WAVELENGTH
Wavelength helps global marketing teams say the right thing, in the right way, in every market — catching what will land and what will flop, grounded in what's actually trending there, not what an LLM assumes.

## The Problem

Global marketing and content teams localize copy (notifications, taglines, captions, ad copy) for different regions, but most teams have no systematic way to know whether a piece of content will actually *resonate* in a target market — only whether it translates correctly. Big companies (e.g., Netflix, Spotify) solve this with dedicated regional marketing teams. Smaller teams don't have that luxury, and even large teams rely on human intuition with no way to verify or scale it.

## Why Not Just Use ChatGPT/Claude?

LLMs can tell you what a translation *means*. They're much weaker at telling you whether it will *land* — whether a reference is culturally salient, whether the tone matches regional norms, or whether there's a current, relevant trend the copy is missing. That's because this requires grounding in **live, region-specific signals** (trending topics, regional norms, cultural references), not a model's static, often US-centric training knowledge. Wavelength grounds every judgment in retrieved regional data and explains *why* something will or won't resonate — not just a vibe-check.

## What It Does

Given a piece of short-form copy and a target region, Wavelength returns:
1. A **cultural fit score** for that region
2. **Flagged issues** — e.g., a reference with no cultural salience in the target market, a tone mismatch with regional norms, or a missed opportunity tied to a current local trend
3. A **grounded rewrite direction**, backed by retrieved regional signals rather than a static LLM guess

## Team & Hats

| Person | Hat | Accountable for |
|---|---|---|
| Stuti Patel | Product | Defining target regions/users, the lean canvas, tracking the north-star metric (cultural-fit recall vs. real edits), owning the pitch and demo narrative |
| Riya Puri | Engineering | Building the pipeline end-to-end (copy input → MT baseline → signal retrieval → scoring), API integrations for regional trend/news data, deployment, repo health and CI |
| Vyom Agarwal | Data and Evaluation | Sourcing and licensing real region-pair localization examples, designing the eval harness and baselines (raw MT, raw LLM prompt), running error analysis against the literature |
| Mokshda Gangrade | Users and Research | Building the core NLP scoring/marker-extraction model, recruiting bilingual/regional users to test flagged copy, running sessions and collecting real usage evidence |

## Repo Structure

```
.
├── reports/        # Weekly reports, lean canvas, evaluation write-ups
├── src/            # Core pipeline and application code
├── data/           # Datasets and annotation guidelines (see licensing notes in reports/)
└── README.md
```


### Brand drafts and history

The authenticated MongoDB user profile supplies company name, industry, tone, description, audience, products, and saved style examples. Settings supports all 50 US states and the existing three India markets. The composer generates captions, notifications, meme concepts, emails, and newsletters through the configured OpenAI-compatible provider (including Gemini). Recent account history supplies context for follow-up requests; the History page shows the latest 100 briefs and responses. Recent weather, trends, news, calendar, and events from the data pipeline’s `state_signals_daily` MongoDB collection now ground US drafts when available; email sending remains a stub. Empty or truncated model output is reported as a generation failure rather than displayed as a draft.

Offline regression checks: `cd src/backend && python3 -m unittest test_generation -v`.


### Regional API context

Run `data/pipeline/run_extract.py` to fetch source responses, then `data/pipeline/load_mongo.py` to load them. Configure the pipeline with the same MongoDB URI and database as the backend (`MONGODB_URI` / `MONGODB_DB_NAME`; legacy `MONGO_URI` is supported by the loader). The extractor needs the dependencies in `data/pipeline/requirements.txt` and source keys for keyed APIs. Generation reads the latest state document from today or yesterday, caps each list at three items, and skips failed, national, guessed, and mismatched state sources. Weather represents the capital city. Missing data does not block drafting. The API data must be refreshed by rerunning the pipeline; generation does not trigger extraction.

Drafts and history render basic Markdown (bold, italic, headings, lists, inline code) with source HTML escaped. The run log has been removed from the app.


### Hosted Hugging Face inference (current configuration)

Set `HF_TOKEN` in `src/backend/.env` to a Hugging Face token with **Make calls to Inference Providers** permission. The app uses `https://router.huggingface.co/v1` and `Qwen/Qwen3-4B-Instruct-2507`. Only models served by Inference Providers can be called; a Hub repository alone does not guarantee hosted availability. Hosted inference consumes account credits and remains subject to provider limits. Restart the backend after editing configuration. No model download is needed.


State generation now includes every supported nonempty successful source type: weather, news, trends, calendar, events, confirmed social posts, and national sports, attention, and YouTube. National scope and guessed Reddit geography remain explicit in the prompt and source details. Payloads include up to ten items per list with text capped at 500 characters; source URLs are omitted. Missing, failed, unconfirmed, unreliable, or mismatched sources are skipped.
