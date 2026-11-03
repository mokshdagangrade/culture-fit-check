---
team: Wavelength
session: 09
date: 2026-11-02
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
 note: >
   This metric describes the copy-scoring product in the original README, not
   the generator the team now builds, so it has never been measurable.
   Replacement proposed for session 10: precision@3 of selected signals
   against human judgement, reported with recall of usable signals.
---

## Shipped this week

- Added hosted image/poster generation using Cloudflare FLUX, with generated images saved in project libraries and History.
- Connected visual prompts to the caption, original brief, brand details, and project references; removed product-specific prompt templates.
- Added product, style, setting, and logo uploads as actual inputs to reference-image generation, with project logos overriding brand settings.
- Improved upload validation, provider error messages, and chat composer alignment; documented the workflow in README.
- Added a retrieval evaluation harness (`training/make_retrieval_review.py`, `training/score_retrieval_review.py`): builds a stratified manual review set from the cleaned signal snapshot and scores it once labelled. 11 new tests; 30 pass in `training/`.

## User evidence

- Feedback identified unrelated visual elements, an unintended third-party logo, and the need to integrate actual product photos into campaign images.
- Updated prompts and reference-image support in response; the user confirmed the corrected chat alignment worked.
- Feedback is qualitative; no new independent user study or measured localization improvement was recorded.
- No human-labelled retrieval data exists yet: the 290-row review set and annotation protocol are ready, but no reviewer has labelled a row, so no retrieval number is reported this week.

## Metrics snapshot

- 21 mocked image-generation tests pass; Python syntax and whitespace checks pass.
- Live Cloudflare generation succeeded with a synthetic reference and a saved project's references.
- Supports three image references plus one logo; PNG/JPEG/WebP uploads are limited to 1 MB and 16 megapixels each.
- Safety-gate refusal rate on the 2026-10-20 snapshot: **7.6%** of candidates (2,631 of 34,532). By source: trends **26.1%**, social 17.7%, news 11.6%, events 3.8%, sports 0%. Categories: politics 978, death 902, violence 325.
- Measured on: the 2026-10-20 cleaned snapshot (`signal_candidate`, 37,788 rows, one day; not a held-out split). Is this the same model running in the product? **Yes** for the gate and candidate pool — produced by the shipped `trend_service.unsafe_reason` and `candidate_service.get_candidate_pool`. Ranking was skipped, so no ranker figure is reported.

## What did not work

- Hugging Face billing requirements blocked hosted generation; added Cloudflare as an alternative.
- Early visuals included unrelated elements and invented branding; replaced generic scene assumptions and fixed overlays with campaign-specific planning and reference-image generation.
- One Cloudflare request returned HTTP 400/code 3030; a later retry succeeded, leaving the original cause unconfirmed. Added clearer diagnostics.
- The north-star metric has read TBD for nine consecutive sessions. Diagnosis: it specifies a scoring product the team stopped building in October, so no work toward it could have produced a number. It needs replacing, not pursuing.
- Lexical retrieval over these signals does not work: TF-IDF cosine between a seasonal-launch brief and the Texas pool peaked at **0.037**, with top matches being event titles containing the word "friends" (band names). Signal texts average 40 characters of proper nouns. Recorded as a negative result, and the reason ranking is an LLM call rather than a vector search.

## Challenges / blockers

- Generated edits can alter product or logo details; exact fidelity requires review.
- Provider quotas, access restrictions, and content review can interrupt generation.
- Project-creation uploads are not automatically visual references; caption writing does not visually inspect images, and PDF/Office extraction remains unsupported.
- Poster layouts and broader browser/device testing need further work.
- Only one day of signals has ever been collected (2026-10-20) and nothing schedules the pipeline, so retrieval serves a snapshot now 14 days old and `candidate_service` reports `empty-pool` silently when nothing is loaded. No temporal evaluation is possible until collection runs daily.
- Two safety-gate defects found: voter-registration phrasing passes (`\bvote\b` does not match "voter", so "Updated voter address" and "polling place change" get through), and event titles are over-refused ("Five Finger Death Punch", "Day of the Dead River Parade"). The labelling session will quantify the second.

## Next week's goal

- Evaluate visual relevance and product/logo fidelity across multiple brands and campaigns.
- Improve reference selection, poster layouts, and recovery from provider failures.
- Run broader end-to-end/mobile checks and collect structured user feedback.
- Label the 290-row review set and report precision@3, recall of usable signals, top-1 agreement and Cohen's kappa, replacing the TBD north-star with a measured number.
- Schedule the daily extract so a second day of signals exists.

## Individual contributions

- Stuti Patel (Product): To be added.
- Riya Puri (Engineering): To be added.
- Vyom Agarwal (Data&Eval): Built the retrieval evaluation harness — `make_retrieval_review.py` generates a stratified, deduplicated review set (brand x state x brief cells, source-balanced, model scores withheld and order shuffled so reviewers cannot anchor, gate refusals included as labelled rows), and `score_retrieval_review.py` scores it into precision@3, recall of usable signals, top-1 agreement, per-source breakdown, gate precision and Cohen's kappa, each with its denominator. Added 11 tests; wrote the 0/1/2 annotation protocol. Measured the shipped safety gate across the full snapshot (7.6% refused, 26.1% of trends) and found two concrete defects. Established as a negative result that lexical retrieval is unusable here, justifying the LLM ranker. Diagnosed the nine-session TBD north-star and proposed a measurable replacement.
- Mokshda Gangrade (Users&Research): Implemented hosted image/poster generation, campaign-specific visual planning, reference/logo uploads, storage/downloads, diagnostics, and chat layout fixes. Added regression tests and checked live reference generation.

## Lean canvas changes (if any)

- No formal changes recorded. Added campaign visuals in response to the previously requested image/poster capability.
- Risk surfaced: the regional-grounding value proposition rests on a signal pool that is roughly 40% national content identical across all 50 states, refreshed by hand. Neither is visible to a user, and neither has been measured against human judgement yet.