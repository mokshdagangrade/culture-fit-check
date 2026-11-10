---
team: Wavelength
session: 10
date: 2026-11-09
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
 previous: TBD
 note: >
   The replacement metric proposed in session 09 is adopted but not yet
   measurable: the review set was labelled, but the ranker could not run
   because the configured model is not routable through Hugging Face
   Inference Providers, so no row carries a model rank. The supply side of
   the same study did produce the project's first measured retrieval number:
   9.1% of gate-passed candidates (21 of 230) were rated "would use" by a
   human reviewer. Ranking numbers follow once the provider is switched.
---

## Shipped this week

- Labelled the full 290-row retrieval review set and produced the project's first measured retrieval figures: per-source human usability, safety-gate precision, and the share of samples with no usable signal at all.
- Fine-tuned Qwen3-4B-Instruct-2507 with LoRA on the held-out brand corpus — the first trained model in the project. 809/98/97 split, bf16 LoRA (r=16, all-linear), 153 steps in 14m24s on an RTX A6000.
- Aligned training prompts with serving prompts: `prepare_data.py` now builds each training turn with the backend's own `build_context_prompt`, so the adapter trains on the format it meets at inference. Median prompt grew from ~145 to ~529 tokens.
- Added `training/merge_adapter.py` to merge the adapter into base weights for vLLM or GGUF serving.
- Made `train.py` portable across machines and library versions: quantization chosen from available VRAM (bf16 above ~22 GiB, QLoRA below), batch and accumulation sized from the card, FlashAttention-2 when the GPU supports it, NEFTune, and a run report recording GPU, dtype, quantization and effective batch.
- Hardened the review tooling after the first labelling pass exposed three defects: cross-run deduplication, UTF-8 BOM on CSV export, and a fail-fast check when the ranker has no provider configured.
- Wrote a Zaratan pre-flight script that checks GPU allocation, compute-node egress, scratch space and SSH tunnelling in one job, ahead of moving inference to UMD's cluster.

## User evidence

- No new user study this week. Evaluation work was offline against the labelled review set and the held-out brand corpus.
- A manual review rubric was drafted covering brand voice, factual accuracy, campaign relevance and cultural appropriateness, including guidance for the case where no local signal is available — separating acceptable brand-only copy from unsupported regional claims.
- Google Ads Transparency Center was explored as a source of real campaign examples filterable by advertiser, region and date, with a capture schema defined per example: brand, source, date, market, channel and the specific localization observed. Regional coverage and provenance gaps remain unresolved, so it is not yet usable as training or evaluation material.
- The 290 retrieval labels are **model-proposed and human-reviewed, with zero overrides recorded**. They are usable as a development set, but they are not independent human judgements and are not treated as a ceiling.

## Metrics snapshot

- **Fine-tuning run.** Qwen3-4B-Instruct-2507, LoRA r=16/alpha=32 on all linear layers, bf16 (no quantization), effective batch 16, 153 optimizer steps, 14m24s on an RTX A6000 (47 GiB), transformers 5.22.2.
- **Validation loss by epoch: 1.9353 → 1.8994 → 1.9225.** Best at epoch 2; epoch 3 regressed, and `load_best_model_at_end` retained checkpoint-102. Correct epoch count found empirically, not assumed.
- Effect size is small: 0.036 nats from epoch 1 to epoch 2, perplexity 6.92 → 6.68. Whether that improves the copy is not answerable from loss.
- **Human usability of retrieved signals, 290 labelled rows:** 21 of 230 gate-passed candidates (9.1%) rated "would use". By source — calendar 50.0% (2/4), social 16.4% (11/67), events 6.7% (5/75), news 5.9% (3/51), **trends 0% (0/26)**, attention 0% (0/2), sports 0% (0/3), youtube 0% (0/2).
- **14 of 30 samples had no usable signal at all.** This is a candidate-supply result, not a ranking result.
- **Safety gate precision: 66.7%** — 40 of 60 refusals were also rated unusable by a human. The remaining 20 are over-refusals.
- Ranker precision@3, recall and top-1 agreement: **not measured.** Every row recorded `rank_method: fallback:no-llm`, so no model rank exists to score against.
- Cohen's kappa: not available. `overlap.csv` has not been labelled independently.
- Training data: 809 train / 98 validation / 97 test from `brandvoice_briefs` only, split by connected group so no prompt, completion or brand crosses splits. The 97-row test split remains sealed.
- Is this the same model running in the product? **No, in two places.** The adapter is not served anywhere yet, and the ranker's provider is unresolved. The gate and candidate-pool figures were produced by the shipped `trend_service` and `candidate_service`.

## What did not work

- **Hugging Face Inference Providers blocked the ranker.** `Qwen/Qwen3-4B-Instruct-2507` returned HTTP 400 `model_not_supported`: it is served by exactly one provider (Nscale), which is not routable for this account, despite being enabled in settings and having billed 12 requests on 2026-10-06. This is the second hosted-provider availability failure in two sessions, after the image-generation billing block.
- The review builder fell back to an unranked run **silently**. The script stubs out `db.py` to read parquet without Mongo, and `db.py` is where the backend loads its `.env`, so no provider key was visible. Fixed by loading the environment in the script and failing fast when the ranker has no provider.
- The first review build wasted two thirds of its budget: 300 rows contained only **106 distinct signals**. National sources have almost no variety for the whole country — `attention` contributed 1 distinct signal across 30 rows, `sports` 1 across 30 — so the same items recur in every state's pool. Fixed with a cross-run deduplication cap; the rebuilt set is 290 rows and 290 distinct.
- The first CSV export was unreadable in Excel: written as plain UTF-8 with no byte-order mark, so non-ASCII signal text rendered as mojibake. The scorer then failed with `KeyError: 'row_id'` because the reader did not strip the BOM once it was added.
- Three environment failures in the training script, none of them data problems: Qwen3's chat template does not render a full conversation as an extension of its generation prompt, so a prefix assertion fired on valid examples; `apply_chat_template(tokenize=True)` returns a `BatchEncoding` rather than a list in current transformers; and `warmup_ratio` was removed from `TrainingArguments` in transformers 5.x.
- `trends` — the signal the product is named after — produced **zero** usable hooks across 26 labelled rows.
- `marketing_instruct` was excluded from training after inspection: 1,307 of its 8,441 targets contain bracketed placeholders such as `[X]`, and 1,260 open with a markdown heading. Training on them would teach the output format the product must not produce.

## Challenges / blockers

- Ranking cannot be measured until the ranker has a working provider. The fix is to point `LLM_BASE_URL`/`LLM_MODEL` at a provider with a free tier; the ranker does not need to be the same model as the generator.
- The 290 labels have zero human overrides, so agreement cannot be computed from them. An independent pass over the 50-row `overlap.csv` is needed before any of the figures above have a ceiling.
- Still only one day of signals (2026-10-20), and still no scheduler in the repository. Every retrieval number is measured on a single October Monday and cannot generalize across time.
- Once the gate is tuned using these 290 rows, they stop being a test set. A second set from a different snapshot day is needed to report a held-out gate improvement.
- The environment runs transformers 5.22.2 while `requirements-train.txt` pins 4.57.1. The training script now works on both, but the pin no longer describes what was used.
- Serving the adapter needs a GPU at demo time. Zaratan can provide one, but a compute node is reachable only through an SSH tunnel by the person who opened it, and queue wait is outside the team's control.
- Semantic duplication and campaign overlap in the training corpus could inflate evaluation scores without reflecting generalization to new brands; group-based splitting addresses exact overlap but not paraphrase.

## Next week's goal

- Switch the ranker to a reachable provider and report precision@3, recall of usable signals and top-1 agreement on the labelled set.
- Run the three-way generation comparison — base model zero-shot, base plus few-shot retrieval from the brand corpus, and the adapter — on unseen brands, scored for brand voice, factual accuracy and regional relevance.
- Label `overlap.csv` independently and report Cohen's kappa.
- Fix the two known gate defects (voter-registration phrasing passing, event titles over-refused) and re-measure on a fresh snapshot rather than the development set.
- Schedule the daily extract so a second day of signals exists.
- Merge the adapter and stand up a local serving path so the demo does not depend on a hosted provider.

## Individual contributions

- **Stuti Patel (Product):** Explored evaluation criteria that distinguish real regional adaptation from superficial location drops or forced local references. Outlined a manual review rubric covering brand voice, factual accuracy, campaign relevance, and cultural appropriateness. Defined reviewer guidance for cases where local signals are unavailable — separating acceptable brand-only copy from unsupported regional claims. Identified product and logo fidelity as evaluation criteria for campaign visuals, alongside consistency between captions and generated images.
- **Riya Puri (Engineering):** Reviewed QLoRA and DPO as approaches for improving brand-voice consistency and incorporating thumbs feedback as a preference signal. Identified the mismatch between generic marketing instruction datasets and the need for finished, brand-specific copy as a core data quality problem for fine-tuning. Noted that semantic duplication and campaign overlap in training data could inflate evaluation scores without reflecting generalization to new brands. Outlined a comparison approach using base-model vs. adapter outputs evaluated on unseen brands, factual accuracy, and regional relevance.
- **Vyom Agarwal (Data&Eval):** Labelled the 290-row retrieval review set and reported the project's first measured retrieval figures — 9.1% human-rated usability of gate-passed candidates, per-source breakdown, 66.7% safety-gate precision, and 14 of 30 samples with no usable signal. Trained the first model in the project: a bf16 LoRA on Qwen3-4B-Instruct-2507, validation loss bottoming at epoch 2 with the best checkpoint retained. Aligned training prompts with serving prompts by building training turns through the backend's own `build_context_prompt`, removing a train/serve mismatch that would have left the adapter out of distribution. Excluded `marketing_instruct` from training on measured grounds. Made `train.py` portable across GPUs and transformers versions, and added `merge_adapter.py`. Fixed three defects in the review tooling found by using it. Diagnosed the Hugging Face routing failure that blocks ranking.
- **Mokshda Gangrade (Users&Research):** Explored Google Ads Transparency Center as a source for campaign examples filterable by advertiser, region, and date. Investigated a manual sampling approach for comparing how brands adapt messaging, seasonal references, and calls to action across markets. Defined a capture schema for each sampled example: brand, source, date, market, channel, and the specific localization observed. Identified gaps in regional coverage and source provenance that need to be resolved before treating public ad examples as training or evaluation material.

## Lean canvas changes (if any)

- No formal changes recorded.
- Risk surfaced: with 9.1% of candidates rated usable and 14 of 30 briefs offered nothing at all, the regional-grounding value proposition is currently limited by signal supply rather than by ranking quality. Improving the ranker cannot raise a number the candidate pool does not contain.
- Risk surfaced: two hosted-provider failures in two sessions, on two different capabilities. Self-hosted serving of the fine-tuned model removes that dependency for generation, and is now the planned path.