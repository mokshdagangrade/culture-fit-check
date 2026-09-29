---
team: Wavelength
session: 05
date: 2026-09-29
members:
 - name: Stuti Patel
   github: stupatel
   hat: Product
 - name: Riya Puri
   github: riyaapuri
   hat: Engineering
 - name: Vyom Agarwal
   github: vyomya
   hat: "Data&Eval"
 - name: Mokshda Gangrade
   github: mokshdagangrade
   hat: "Users&Research"




north_star:
 metric: percentage of real localization edits independently flagged (recall vs. human expert adaptation)
 value: TBD
 previous: N/A
---




## Shipped this week


- Built the initial multi-source data pipeline, integrating 9 external data sources and creating a common structure for their outputs.
- Implemented individual API extractors with standardized schemas, validation, and structured error handling so failures from one source do not break the full pipeline.
- Added state-level data processing for all 50 U.S. states, including stitching data from different sources into a unified state-level representation.
- Integrated national-level sources such as sports and Wikipedia attention data and incorporated them into the overall daily pipeline output.
- Added data quality checks and testing for the extraction and stitching workflow, while accounting for differences in API formats, availability, and coverage across sources.

- Added 9 Census divisions (not just 4 regions) to `us_states.py`, with a validator that checks each state's division matches its region
- Added a `GeoTag` schema with location based `scope` and `confidence` on every source document, so a national signal (e.g. Wikipedia, YouTube) can never be mistaken for state-level data
- Fixed `try_fetch` so a failed extractor call now returns a structured `ErrorDoc` (source, reason, timestamp) instead of silently failing. Failures are now visible per-source in the console and validation report
- Added a MongoDB ingestion utility for idempotent daily upserts
- Fixed a Wikipedia "attention" bug where cross-language Wikipedia home/namespace pages were polluting the `top_articles` list instead of real trending content

- Rebuilt the frontend with a dark default theme and a light-theme toggle. The whole left side is now one chatbot: the prompt, content-type pills (caption / notification / meme), and a paperclip to upload past posts as style examples, which replaces the separate style-examples box. The right side shows an animated agent loop (read brief → learn voice → check weather → scan trends → draft → review) that runs when a brief is sent, then fills in per-state draft cards with a run log
- Reworked the results view into per-state draft cards with thumbs up/down, "Use this", and per-state regenerate, all driven from the chat flow
- Added login/signup checks on both client and server: email format (with typo suggestions such as `gmial.com`), password rules (8+ characters, a letter and a number, 72-byte max), confirm-password, a strength meter, and clear inline errors for duplicate emails or an unreachable backend
- Moved password hashing to `bcrypt` directly in `auth.py` (hash, verify, JWT helpers) and added matching validators in `models.py`, so the rules also hold when the API is called directly. Emails are lowercased so one address is one account

- Connected the frontend chat interface to the backend LLM pipeline, enabling end-to-end user messages and LLM responses directly through the UI.
- Added a modular context-building layer for LLM prompts with placeholders for company details, target location, weather, and Google Trends, allowing future responses to use brand and regional context.
- Added a reusable prompt wrapper that combines user requests with company, location, weather, and trend context before sending the request to the LLM API.


## User evidence


- Discussed the project with friends, shared our vision, and gathered honest feedback to better understand our target audience, their needs, and the potential market reach of the project.
- Had a user walk through the app end to end: sign up / log in, brand setup, then a mock run in the chat, using the current LLM integration Vyom added (trend and state inputs are still mocked).
  - What they liked:
    - The login/signup flow was easy to follow, and the inline messages told them exactly what was wrong with an email or password instead of just failing
    - One chat box for the prompt and file upload made it obvious what to do next, with no separate forms to figure out
    - Watching the agent loop step through made the wait feel purposeful and showed what the tool does with a brief
    - Drafts laid out per state in separate cards made it easy to compare regions and pick favorites
    - The dark theme and overall look felt more fun and polished than a basic form, with light mode available
  - Features they suggested or that came out of the discussion:
    - A history tab to see all past projects and runs
    - A landing page after login that lists projects, where collaborators can be added. Opening a project shows the chatbot on the left and, on the right, what is happening and the results
    - Having the model automatically generate an image for each post alongside its caption




## Metrics snapshot


- Percentage of real localization edits independently flagged: TBD (was N/A)
- Measured on: Initial baseline setup phase
- Is this the same model that is running in the product? Yes — the LLM model evaluated in our test suite is the same OpenAI-compatible model powering our backend endpoints (`llm.py` / `main.py`)
- Executed diagnostic testing (`check_llm.py`) to confirm system readiness and connection integrity across developer environments.
- Test suite pass rate: 100% pass on automated API integration tests (`test_api.py`), validating HTTP 200 responses and HTTP 422 payload rejection.
- Schema & performance validation: Verified end-to-end response schema integrity and execution across simulated multi-region inputs (`US/Texas/Austin` and `India/Maharashtra/Mumbai`).
- 18 automated tests written for extraction, validation, stitching, and error handling.
- 9 active, synchronized data extraction channels operating in harmony (Weather, News, Trends, Attention, Calendar, Social, Sports, Events, YouTube).
- 100% data pipeline resilience achieved: fault-isolated error handling prevents partial API outages from halting the macro state-stitching engine.
- Frontend flows checked in a headless browser against a stubbed API: signup/login validation, style-example upload, a full loop run, per-state regenerate, the error state, dark/light theme, and mobile layout, with no JS errors
- Checked `bcrypt` hashing and signup validation directly: the right password verifies and a wrong one does not, and passwords over 72 bytes are rejected cleanly instead of raising an error. These checks are not yet part of the automated suite
- Verified the end-to-end chat flow from frontend → FastAPI backend → LLM API → frontend response using basic prompts such as "Hi" and "Hello".



## What did not work


- Requesting unstructured text outputs from the LLM for copy evaluation produced parsing variations; required defining structured Pydantic models and fallback stubs to maintain API reliability.
- Static context mocks struggled to reflect complex multi-region slang and local nuances during sanity tests. We continue to enhance and build on this baseline.

- GDELT DOC API rate-limited (429) on nearly every run regardless of throttling interval - unsuitable for a 50-state sequential batch job; it was replaced with an alternative data source.
- Official Reddit API required an approved app, so it was replaced with Arctic Shift.
Official Google Trends API was gated, so the public Trending Now RSS feed was used instead.
- Some sources have limitations such as API keys, rate limits, delayed data, or incomplete state-level coverage.
- Per-Video YouTube Geolocation Tagging: Unable to extract state-level geolocations from individual trending YouTube videos due to hyper-sparse metadata

- A separate style-examples input next to the prompt made the flow feel like two tasks, so it was merged into the single chat with an upload option
- The agent loop animation is currently choreographed on a timer while one request runs, so it shows the intended stages but not real backend progress
- `bcrypt` only reads the first 72 bytes of a password and errors above that, so signup now enforces a limit and login handles longer input safely
- Grok was initially considered for the LLM backend, but API access required paid credits, so we switched to a free-tier model for development and testing.


## Challenges / blockers


- Tailoring evaluation context dynamically per country and region: establishing ground truth for fast-moving cultural, regional, and marketing trends is challenging due to how quickly local contexts shift.
- Differentiating between purely stylistic marketing phrasing versus genuine cultural misalignment during automated evaluation.
- Different APIs returned different data structures and coverage.
- Managing rate limits and failures without stopping the entire 50-state pipeline.
- Some sources lacked reliable state-level mappings, requiring best-effort approaches.
- Making the process view honest: the backend needs to stream real step events so the loop reflects what is actually running, not just a timed animation
- The demo is limited to 3 states in mock mode. Expanding it depends on how well the data sources cover each state, since several are only country-level


## Next week's goal


- Evolve LLM calls to use structured JSON mode natively within `evaluator.py`.
- Connect frontend UI directly to backend `/generate-caption` and `/evaluate-copy` endpoints for end-to-end user testing.
- Upgrade trend retrieval from hardcoded mocks to dynamic geolocation and live weather/trend fetching.
- Curate a benchmark dataset of 50+ localized marketing copy samples to begin measuring baseline accuracy and recall metrics.
- Develop a database structure to efficiently handle and organize different types of data.
- Test the pipeline with live data across all 50 states, improve source coverage/reliability, and finalize the pipeline output for downstream LLM processing.
- Expand the app from the 3 mock-mode states to all feasible states, using the data the pipeline now produces
- Train our model on the open-source data acquired
- Replace the timer-driven agent loop with real step events streamed from the backend
- Scope the features from user feedback: a history tab, a projects landing page with collaborators and a per-project workspace, and automatic image generation for captions
- Replace the current company, location, weather, and trend placeholders in the LLM context layer with live backend data sources and connect the resulting context to production prompt generation.



## Individual contributions


- Stuti Patel (Product): Implemented and integrated API extractors across the extractors/ modules, worked on shared data structures in schemas.py and the pipeline stitching/validation workflow. Added API handling and failure recovery through http_client.py and try_fetch(). Combined source outputs into the unified state-level daily dataset through stitch_state().
- Riya Puri (Engineering): Implemented the `GeoTag` metadata schema tracking spatial scope and confidence levels across all extractors, and integrated new data source APIs and fixed an existing API source, while upgrading pipeline resilience through `ErrorDoc` interception and MongoDB upsert automation (`load_mongo.py`). 
- Vyom Agarwal (Data&Eval): Built the LLM integration logic (`llm.py`) and diagnostic connection check script (`check_llm.py`). Connected the frontend chat interface to the backend LLM pipeline for end-to-end user interaction, and added a modular prompt/context layer with placeholders for company details, location, weather, and Google Trends to support context-aware localized generation.
- Mokshda Gangrade (Users&Research): Constructed the initial base pipeline skeleton, frontend-backend project scaffolding, and repository structure. This week worked across the frontend and backend to give the UI a better flow and bring our vision to life: rebuilt the UI around a single chatbot with an agent-loop view and dark/light themes, added login/signup validation, and moved password hashing to `bcrypt`. The app currently runs in mock mode with 3 states; we plan to expand it to all feasible states and train our model on the open-source data acquired.




## Lean canvas changes (if any)


- None this week. Focus remained on establishing the baseline pipeline, API routes, and testing infrastructure.