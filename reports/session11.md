---
team: Wavelength
session: 11
date: 2026-11-17
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
  metric: precision@3 of selected signals against human judgement, reported with recall of usable signals
  value: not measured
  previous: not measured
  note: >
    Human review rated 21 of 230 gate-passed candidates (9.1%) as
    "would use" signals. Provider routing prevented ranker measurement.
    Context-panel and backend fixes improve correctness and visibility;
    they do not establish improved retrieval or ranking quality.
---


## Shipped this week


- **Fixed the draft context panel** in `src/frontend/js/app.js`. `ctxChips` renders weather and individual `signal_selection.selected` items instead of treating audit objects as source documents. Each signal shows its source category, text, supporting context, available dates, location scope/confidence, AI relevance score, and selection reason. National signals are explicitly US-wide.
- **Corrected counts and empty states.** The panel counts weather plus renderable selected signals, excluding audit records. Missing optional fields and older saved entries no longer produce `undefined` or `null`; empty context shows "No recent state data available." Dynamic text remains HTML-escaped. Scores describe campaign relevance, and supplied context is not presented as proof that the draft used it.
- **Removed the redundant image-history `prompt` assignment** in `src/backend/main.py`. Only the first occurrence before `**result` was removed: history retains the caption in `prompt` and visual instructions in `visual_prompt`, while `/generate-image` returns visual instructions as `prompt`.
- **Fixed the interleave boundary** in `candidate_service.py`, changing `>` to `>=` to avoid an empty final pass. Candidate ordering, source quotas, and the pool cap are unchanged.
- **Clarified retrieval logging** to report missing regional pipeline coverage rather than an unsupported market. Empty-pool behavior is unchanged.
- **Moved `re` to module scope** in `prompt_builder.py` without changing holiday prompt output.
- **Updated the root, data, and training READMEs** with context-panel behavior, image-history fields, regression commands, the training-test limitation, and US-only project scope. The changes preserve API schemas and require no database migration, dependency, or service.
- **Explored open-source image generation models** and prompt-engineering strategies for campaign-specific visual content. Researched alternative models and prompt structures to identify potential improvements in image quality, instruction adherence, brand consistency, and relevance to regional marketing campaigns. Findings will inform future model selection and evaluation.
- Created a structured evaluation framework to assess regional relevance, brand consistency, factual accuracy, and visual quality of generated campaigns.
- Profiled marketing-instruct-8k before it was used: the dataset card describes instruction, input and output, but the files have four columns (original_prompt, original_completion, enhanced_prompt, enhanced_completion), and the card’s row count (about 4.3k) disagrees with the 8,441 rows shown.


## User evidence


- Code review traced the panel defect to different data shapes: weather uses `data`, `scope`, and `confidence`; selected signals use `text`, `context`, `geo_scope`, and `geo_confidence`. The renderer now handles each explicitly.
- The review rubric covers brand voice, factual accuracy, campaign relevance, cultural appropriateness, and product/logo fidelity, including acceptable brand-only copy when local signals are unavailable.
- The 290 retrieval labels are model-proposed and human-reviewed, with zero overrides recorded. They form a development set rather than independent human judgements.
- Google Ads Transparency Center research defined capture fields for brand, source, date, market, channel, and localization choices. No new user study or live-provider evaluation was conducted for these fixes.
- Research explored additional open-source image generation models and prompt-engineering strategies that could improve visual quality, prompt adherence, and campaign-specific generation. This work was exploratory; no production model change or comparative evaluation was completed this week.




## Metrics snapshot


### Validation


- **64 backend/image tests passed**, using mocked database and provider calls.
- **256 interleave combinations matched the original output**, including empty pools and unequal source lengths, without mutating inputs.
- Image responses, history fields, and project image entries matched the original behavior for project and non-project requests. Holiday, empty-signal, and legacy-trend prompts also matched.
- **JavaScript syntax and 28 rendering assertions passed** in JavaScriptCore with a DOM stub, covering counts, missing fields, national/guessed geography, date labels, and HTML escaping.
- **Training tests: 29 passed, 1 error.** The fake tokenizer in `test_training_masks_prompt_and_excludes_overlength` is not callable, while `encode_example` calls it directly. This error is unrelated to the fixes.
- Formatting checks passed. Validation used local checks rather than live MongoDB, hosted generation, GPU serving, or browser interaction.


### Retrieval and training


- **Signal usefulness:** 21/230 gate-passed candidates (9.1%) were rated "would use." By source: calendar 2/4, social 11/67, events 5/75, news 3/51, trends 0/26, attention 0/2, sports 0/3, and YouTube 0/2.
- **Candidate supply:** 14/30 samples had no usable signal. **Safety-gate precision:** 40/60 refusals (66.7%) agreed with human review.
- Ranker precision@3, recall, and top-1 agreement are unmeasured: review rows recorded `fallback:no-llm`. Independent reviewer agreement is also unmeasured.
- **Model:** Qwen3-4B-Instruct-2507, bf16 LoRA rank 16/alpha 32 on all linear layers; 809/98/97 train/validation/test examples from `brandvoice_briefs`, grouped to prevent exact prompt, completion, or brand overlap.
- **Training run:** effective batch 16, 153 optimizer steps, 14m24s on an RTX A6000 with transformers 5.22.2. Validation losses were 1.9353 → 1.8994 → 1.9225; checkpoint-102 at epoch 2 was retained. Loss improvement alone does not establish better copy.


## What did not work


- The context panel displayed audit objects as sources while hiding selected hooks. The renderer correction resolves this defect.
- The fake-tokenizer error prevents a fully passing training suite.
- Hugging Face returned `model_not_supported` for the ranker, preventing ranking evaluation.
- `marketing_instruct` was excluded from training after inspection found placeholder-heavy and heading-heavy targets that conflict with finished-copy output.
- The 40 of 60 gate refusals that humans agreed with (66.7%) means a third of refusals blocked usable signals, so the gate trades safety against supply.


## Challenges / blockers


- Ranker measurement requires a working provider; adapter generation requires a verified GPU serving path.
- Retrieval evidence covers one snapshot day, 2026-10-20. A fresh snapshot and scheduled refresh are needed for evaluation across dates and independent gate checks.
- The 50-row overlap set needs independent labels. Campaign-example coverage and provenance also need review before use as training or evaluation material.
- The training environment used transformers 5.22.2 while `requirements-train.txt` pins 4.57.1. Exact grouping does not eliminate semantic or campaign overlap.
- Partial-state recovery is deferred: one generation failure can still fail the whole request. Retry design must address stale drafts/errors, result order, saved retry targets, follow-up context, and network/history-save failures. Returning partial `200` responses instead of `502` changes API behavior.
- Existing non-US region options need reconciliation with the documented US-only scope.
- Existing non-US region options conflict with the documented US-only scope, so users can pick regions the product doesn't support. 
- Trends contributed nothing usable in this sample, yet they were the largest source in the safety-refusal analysis, so the pool is weaker than its size suggests. 


## Next week's goal


- Implement separately approved partial-state recovery to preserve successful drafts and retry only failed US states.
- Check the context panel in a live browser with saved and newly generated drafts; fix the training fake-tokenizer mismatch.
- Restore ranker access, report precision@3 and recall together, and independently label the overlap set.
- Compare base zero-shot, base with examples, and adapter generation on unseen brands; verify adapter serving.
- Collect a fresh snapshot before measuring voter-registration filtering and event-title over-refusal changes; automate refresh and align region options with US-only scope.


## Individual contributions


- **Stuti Patel (Product):** Defined criteria for regional relevance, factual accuracy, brand voice, cultural appropriateness, and visual product/logo fidelity, including review guidance for drafts without usable local signals. Explored alternatives for the blocked ranker path after Hugging Face returned `model_not_supported`, scoping which hosted or open-source models could replace it and what a precision@3 and recall run would need.
- **Riya Puri (Engineering):** Fixed the context panel to expose weather and selected signals with accurate counts, date/location labels, relevance scores, missing-field handling, and HTML escaping. Preserved image-history field meanings while removing the duplicate assignment, corrected the interleave boundary and coverage log, and moved `re` to module scope. Verified 64 backend/image tests, 256 interleave comparisons, image-history/prompt compatibility, and 28 frontend rendering assertions. Updated the READMEs and US-only scope wording, documented the unrelated training-test error, and reviewed partial-retry behavior.
- **Vyom Agarwal (Data&Eval):** Reviewed LoRA training and data splits for brand consistency and leakage risks. Checked retrieval metrics for sampling limits and missing evidence, investigated stale data and filtering errors, and outlined base-versus-fine-tuned model evaluation on unseen brands.
- **Mokshda Gangrade (Users&Research):** Investigated regional campaign examples through Google Ads Transparency Center and defined capture fields and provenance checks for evaluating localization choices. Researched additional open-source image generation models and explored prompt-engineering approaches for improving image-generation quality, instruction following, and campaign relevance.


## Lean canvas changes (if any)


- US states and regions define the project scope; no other formal canvas changes.
- The context panel makes supplied evidence inspectable without claiming improved cultural fit. Limited usable signal supply and provider availability remain the main product risks.

