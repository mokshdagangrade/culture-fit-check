---
team: Wavelength
session: 07
date: 2026-10-20
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

- Integrated two Hugging Face datasets into the data pipeline: suehuynh/marketing-instruct-8k and manifesta/brandvoice-marketing-briefs.
- Added check_hf_datasets.py to extract the datasets and export their records as JSON for downstream processing.
- Updated json_to_tables.ipynb to convert the extracted JSON datasets into Parquet files under out/tables/reference_datasets/, making them easier to use in subsequent data processing and evaluation.
- Removed the separate notebook-level requirements file to consolidate dependency management in the pipeline requirements.
- Converted JSON documents into Parquet tables for analysis and training preparation.
- Separated regional and national data to avoid repeated storage.
- Standardized text, URLs, and dates across sources.Removed repeats when state, collection date, URL, and title matched.
- Flagged uncertain duplicates, noise, date issues, and location conflicts.
- Added configurable lookback and lookahead windows for each source.
- Cached annual US calendars to reduce API requests.
- Added bounded event pagination and daily sports collection across nine leagues.
- Used temporary scripts to resume event and Reddit collection from saved positions.
- Added validation tests and quality reports to identify missing data and coverage gaps.
- Added load_candidates.py to load cleaned signal candidates from Parquet into MongoDB.
- Built candidate retrieval with state and national scope, freshness checks, duplicate/noise filtering, sensitivity screening, and source quotas.
- Added an LLM ranker that selects up to three campaign-relevant signals and records scores and selection reasons.
- Connected selected regional signals to marketing prompt generation.
- Inspected the brand and marketing datasets and built a reproducible training-data preparation pipeline with brand metadata, deduplication, traceable manifests, and held-out splits.
- Selected Qwen3-4B-Instruct-2507 as the initial pretrained model and implemented a QLoRA training recipe for later execution on Zaratan.
- Added a separate generation endpoint configuration for serving the trained adapter.
- Refined RAG integration to exclude unranked context, preserve geographic scope, and make weather optional.
- Fixed timestamp handling in the cleaning notebook and enabled holiday retrieval through Calendarific.
- Prioritized current and upcoming holidays in candidate selection and strengthened holiday-specific generation instructions.

## User evidence
- The two datasets provide reference material for developing and evaluating localized marketing content, but their usefulness for identifying genuine cultural misalignment still needs to be validated against human judgments
- Retrieval audits make it possible to inspect which signals were considered, rejected, and selected for each campaign; human relevance validation remains pending.
- Manual testing with a JustRight DIY sneaker campaign exposed missing holiday data, ranker failures, and generic wording despite available context.
- Confirmed that Halloween entered live retrieval pools after configuring calendar access and adjusting holiday prioritization.
- These are developer-led checks, not independent user validation or evidence of improved localization recall.

## Metrics snapshot

- 50 states; 37,788 candidates, up from 11,095: 27,406 events, 8,856 cleaned Reddit posts, and 500 news articles.
- 400 dated attention-history rows, 18 passing tests, 30 passing cleaning checks
- Marketing-Instruct dataset: 8,441 rows of marketing copywriting examples.
- BrandVoice Marketing Briefs: 6,403 source rows covering 83 brands, plus 64 marketing-craft principles; the adapted dataset contains 6,366 rows.
- Candidate retrieval caps the pool at 40 signals, balances eight source types, and selects up to three signals scoring at least 5/10.
- Inspected local Parquet files containing 8,441 marketing instruction examples and 1,300 brand-brief records.
- The local brand file contains 1,004 writing examples across 83 brands and 296 marketing-principle examples.
- Prepared 9,445 examples: 7,562 training, 942 validation, and 941 test.
- Verified no exact normalized prompt, completion, or brand overlap across splits.
- Latest refresh loaded 1,213 cleaned candidates, including calendar data.
- 37 backend regression tests and two training-data tests pass.

## What did not work

- Reddit backfills timed out in eight states; successfully collected posts were preserved.
- Wider JSON windows alone could not retrieve historical Trends or free-tier news archives. News continuation was also blocked by unsaved pagination tokens.
- An initial filter based on the `task` field removed all rows, indicating that the filtering assumptions did not match the available dataset values.
- Dataset filtering and preprocessing require further validation to avoid unintentionally discarding usable examples.
- Source availability and quota limits can leave some regional candidate pools incomplete.
- LLM ranking can fail, leaving generation without selected regional hooks.
- Mixed timestamp types caused candidate construction to fail before the notebook saved its output; explicit datetime normalization resolved the failure.
- Missing Calendarific credentials initially prevented holiday retrieval.
- Chronological ordering allowed past holidays to consume the calendar quota before upcoming holidays.
- Some drafts remained generic even when Halloween was selected; prompt instructions were strengthened.
- The frontend incorrectly counted retrieval audit objects as data sources; this display issue remains unresolved.

## Challenges / blockers

- Tailoring evaluation context dynamically per country and region: establishing ground truth for fast-moving cultural, regional, and marketing trends is challenging due to how quickly local contexts shift.
- Differentiating between purely stylistic marketing phrasing versus genuine cultural misalignment during automated evaluation.
- Different APIs returned different data structures and coverage.
- Managing rate limits and failures without stopping the entire 50-state pipeline.
- Some sources lacked reliable state-level mappings, requiring best-effort approaches.
- Making the process view honest: the backend needs to stream real step events so the loop reflects what is actually running, not just a timed animation
- The demo is limited to 3 states in mock mode. Expanding it depends on how well the data sources cover each state, since several are only country-level
- Event IDs and exact start times are missing from current tables, limiting duplicate accuracy. Flagged records still require review before training selection.
- Defining filtering and preprocessing rules without losing relevant marketing examples.
- Keeping the two datasets separate, with independent train/test splits, so their records and evaluation results remain traceable.
- Determining whether the available examples contain sufficient regional and cultural information to support localization evaluation.
- Verifying the output paths, schemas, and record counts of the generated JSON and Parquet files.
- Establishing a reliable evaluation benchmark based on human judgments of genuine localization edits rather than stylistic differences alone.
- Measuring campaign relevance requires human-reviewed examples; LLM scores alone are not ground truth.
- National signals and inferred state geography must remain explicit to avoid overstating local relevance.
- Ranking reliability and incomplete source coverage limit consistent grounding.
- GPU training and adapter-serving verification remain pending on Zaratan.
- Brand-writing examples do not provide regional-fit labels or trend-ranking supervision.
- The general marketing dataset substantially outnumbers brand-specific examples, requiring evaluation of the training mixture.
- Dataset provenance, unsupported product claims, and semantic overlap require further review.
- News, events, YouTube, and Wikipedia require additional configuration; Trends requires its missing dependency.

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
- Fix the task-filtering logic and confirm that valid examples are retained.
- Verify the record counts, fields, and output paths for the JSON and Parquet files.
- Finalize independent train/test splits for each dataset and document the preprocessing decisions.
- Connect the prepared datasets to the downstream model-development and evaluation workflow.
- Improve retrieval coverage and ranker reliability across states.
- Review selected and rejected signals with human annotators to build a relevance evaluation set.
- Evaluate whether ranked signals improve campaign relevance over a brand-and-brief baseline.
- Run a QLoRA smoke test and initial fine-tuning job on Zaratan.
- Compare the base model and trained adapter on brand voice, brief adherence, format compliance, and unsupported claims.
- Serve the adapter and verify generation with live retrieved context.
- Fix the frontend source display to show actual selected signals and distinguish empty retrieval from ranking failure.
- Test holiday grounding across formats and states.

## Individual contributions

- Stuti Patel (Product): Integrated two Hugging Face marketing datasets into the existing pipeline, developing a configurable extraction workflow with schema validation, missing-value handling, and data quality checks. Updated `json_to_tables.ipynb` to support downstream Parquet integration. Investigated dataset filtering behavior, analyzed task distributions, and identified a restrictive filter that excluded all records.
- Riya Puri (Engineering): Built a cleaner, reusable dataset for regional marketing research: separated state and national signals, standardized text/URLs/dates, and removed confirmed within-state news and Reddit repeats. Added configurable source age windows, quality reports, and incremental collection to expand coverage while preserving existing data and API quota.
- Vyom Agarwal (Data&Eval): Implemented MongoDB loading for cleaned candidates, balanced regional retrieval, sensitivity filtering, and LLM-based relevance ranking. Connected selected signals to generation and added selection scores, reasons, and retrieval audits.
- Mokshda Gangrade (Users&Research): Prepared brand-conditioned training datasets and held-out splits, selected Qwen3-4B, and implemented QLoRA training and adapter integration configuration. Tested campaign generation, repaired cleaning and holiday-retrieval issues, and refined prompts to use relevant selected context.

## Lean canvas changes (if any)

- None this week. Focus remained on establishing the baseline pipeline, API routes, and testing infrastructure.
