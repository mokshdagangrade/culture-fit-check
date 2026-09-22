---
team: Wavelength
session: 03
date: 2026-09-15
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

- Established backend scaffolding connecting frontend and FastAPI backend via CORS middleware and `.env` setup.
- Curated and integrated initial regional data sources for localized context grounding.
- Built the `POST /evaluate-copy` REST endpoint in `main.py`.
- Developed `evaluator.py` to calculate 0–100 cultural fit scores, flag issues by severity, and generate localized rewrites.
- Defined `EvaluateRequest` and `EvaluateResponse` Pydantic models for strict payload validation.
- Implemented structured fallback stubs in `evaluator.py` to ensure API reliability during LLM timeouts or failures.
- Created a unified LLM client interface in `llm.py` to handle system prompts, model parameters, and error catching.
- Built `check_llm.py` as an interactive CLI tool to verify API keys, connection status, and LLM reachability.
- Created `trend_retrieval.py` (`get_mock_context`) to inject regional climate, trends, and slang into prompts.
- Developed an automated integration test suite (`test_api.py`) using `pytest` and FastAPI's `TestClient`.


## User evidence

- Established initial baseline testing and pipeline scaffolding to prepare for live user task testing.

## Metrics snapshot

- Percentage of real localization edits independently flagged: TBD (was N/A)
- Measured on: Initial baseline setup phase
- Is this the same model that is running in the product? Yes — the LLM model evaluated in our test suite is the same OpenAI-compatible model powering our backend endpoints (`llm.py` / `main.py`)

- Executed diagnostic testing (`check_llm.py`) to confirm system readiness and connection integrity across developer environments.
- Test suite pass rate: 100% pass on automated API integration tests (`test_api.py`), validating HTTP 200 responses and HTTP 422 payload rejection.
- Schema & performance validation: Verified end-to-end response schema integrity and execution across simulated multi-region inputs (`US/Texas/Austin` and `India/Maharashtra/Mumbai`).


## What did not work

- Requesting unstructured text outputs from the LLM for copy evaluation produced parsing variations; required defining structured Pydantic models and fallback stubs to maintain API reliability.
- Static context mocks struggled to reflect complex multi-region slang and local nuances during sanity tests. We continue to enhance and build on this baseline.

## Challenges / blockers

- Tailoring evaluation context dynamically per country and region: establishing ground truth for fast-moving cultural, regional, and marketing trends is challenging due to how quickly local contexts shift.
- Differentiating between purely stylistic marketing phrasing versus genuine cultural misalignment during automated evaluation.

## Next week's goal

- Evolve LLM calls to use structured JSON mode natively within `evaluator.py`.
- Connect frontend UI directly to backend `/generate-caption` and `/evaluate-copy` endpoints for end-to-end user testing.
- Upgrade trend retrieval from hardcoded mocks to dynamic geolocation and live weather/trend fetching.
- Curate a benchmark dataset of 50+ localized marketing copy samples to begin measuring baseline accuracy and recall metrics.

## Individual contributions

- Stuti Patel (Product): Researched, curated, and added initial localized data sources for trend contextualization.
- Riya Puri (Engineering): Implemented the `/evaluate-copy` endpoint, `evaluator.py` engine, Pydantic data schemas, and the `test_api.py` test suite.
- Vyom Agarwal (Data&Eval): Built the LLM integration logic (`llm.py`) and diagnostic connection check script (`check_llm.py`).
- Mokshda Gangrade (Users&Research): Constructed the initial base pipeline skeleton, frontend-backend project scaffolding, and repository structure.

## Lean canvas changes (if any)

- None this week. Focus remained on establishing the baseline pipeline, API routes, and testing infrastructure.