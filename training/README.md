# Marketing generator training

Dataset preparation, LoRA fine-tuning and adapter export for the draft
generator. Serving the result is in [`serving/README.md`](../serving/README.md).

## Ranker review export and regression tests

From the repository root, use an existing backend environment or create one:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r src/backend/requirements.txt
python -m unittest discover -s training -p 'test_*.py' -v
PYTHONPATH=src/backend python -c 'import fastapi, unittest; unittest.main(module=None)' test_backend test_generation test_projects test_image_generation -v
```

These tests mock model and database calls; they need no API keys, MongoDB server,
GPU, or training datasets. FastAPI is loaded before the backend tests because
their existing `sys.modules` patches otherwise reload its exception class.
The older `test_api.py` targets retired endpoints and is not part of this command.

Current state: 30 training tests run, 29 pass, and
`test_training_masks_prompt_and_excludes_overlength` errors because its fake
tokenizer is not callable — `train.encode_example` now calls the tokenizer
directly for the completion. This is a real coverage gap, not a baseline to live
with: that function broke twice during the first GPU run (a chat-template prefix
assertion and a `BatchEncoding` return type) and the test that should have caught
both does not execute. Fix the fake tokenizer before the next training change.

Save the authenticated `/history` JSON response, then export candidate pairs:

```sh
python training/export_ranker_reviews.py history.json --output training/out/ranker_reviews.jsonl
```

The exporter accepts a history response or an array of history entries. It leaves
human relevance, suitability, notes and reviewer fields blank, and refuses to
overwrite an existing file. Unassessed candidates have a null model score, not
a negative label. Older history only supplies scores for selected signals and
has no saved company snapshot. Only newly generated history contains the full
assessment audit. Assessing every candidate uses more output tokens than selecting
three; provider cost, latency and scoring quality still need live evaluation.

## Data preparation

Run from the repository root:

```sh
python -m pip install -r training/requirements.txt
python training/prepare_data.py
python -m unittest discover -s training -p 'test_*.py' -v
```

PyArrow 19 failed to read these files with `Repetition level histogram size
mismatch`; PyArrow 26 reads them. Backend dependencies are unchanged.

The preparation command writes ignored artifacts under `training/out/`:

- `train.jsonl`, `validation.jsonl`, `test.jsonl`: system/user/assistant messages.
- Matching `*.manifest.jsonl` files: source rows, brand, normalized prompt and
  completion hashes for auditing. Do not pass manifests to the trainer.
- `report.json`: input checksums, exclusions, split sizes, completion lengths
  and prompt-length statistics.

`--sources` defaults to `brandvoice_briefs` alone. `marketing_instruct` and the
296 marketing principles are included only when asked for explicitly
(`--sources all`, or `--include-principles`). When `marketing_instruct` is
included, the original and enhanced prompt/completion variants are never both
used; `--marketing-variant original` selects the original pairs and excludes rows
with missing completions. No completion is fabricated for a missing target.

That default matters for interpretation: the instruction corpus outnumbers brand
examples by about 8:1, so a run with `--sources all` is mostly learning generic
marketing-instruction following. Compare brand-only against mixed training on
held-out brand tasks rather than assuming more data is better.

### Prompt shape

`--prompt-style` defaults to `serving`, which builds each training turn with
`prompt_builder.build_context_prompt` — the same function the backend serves
with. `flat` keeps the older bare-brief format.

This is not cosmetic. Measured on the current dataset, the median prompt grows
from 581 characters / 145 tokens under `flat` to 2,118 characters / 529 tokens
under `serving`. Training on `flat` and serving with the real builder teaches the
adapter to continue a string it will never be shown, so leave the default alone
unless you are deliberately measuring that gap.

Splits target 80/10/10 by source with seed 42 and currently come out 809 / 98 / 97.
Connected groups of repeated normalized prompts, repeated normalized completions,
and the same brand remain together, including connections across datasets. Brand
holdout measures transfer to unseen brands. Group sizes can shift the proportions.
This is exact normalized deduplication, not semantic paraphrase detection or
campaign-family detection; review those before treating evaluation results as
independent.

## Before running model training

The prepared files are training inputs, not a trained model. These datasets teach
marketing writing and brand conditioning; they do not supply regional-fit scores
or brand/signal relevance labels for the ranker. Keep live trends in retrieval.

Review dataset provenance and usage terms, sample targets for unsupported claims,
and check overlap or paraphrases across sources. Some examples ask for frameworks
and explanations, while the app usually asks for finished copy; evaluate that
behavior explicitly.

## Model and training recipe

Use [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
a 4B instruction model under Apache 2.0. Fine-tune brand writing with LoRA; keep
live regional facts in retrieval rather than model weights. This is an initial
baseline, not a claim that it outperforms the hosted providers — that comparison
has not been run yet (see *Not yet done* below).

The recipe targets a single NVIDIA CUDA GPU on Linux. Install and run in an
environment separate from the backend:

```sh
python -m pip install -r training/requirements-train.txt
python training/prepare_data.py
python training/train.py --max-steps 2 --output-dir training/checkpoints/smoke
python training/train.py
```

Defaults: 3 epochs, learning rate 1e-4 with a cosine schedule and 3% warmup,
LoRA rank 16 / alpha 32 on all linear layers, 4096-token context, NEFTune alpha 5,
gradient checkpointing on.

Quantization and batch size are read from the card rather than fixed: bf16 above
22 GiB of VRAM and 4-bit NF4 below it, batch 4 on a 40 GiB+ GPU scaling down to 1,
with gradient accumulation targeting an effective batch of 16. FlashAttention-2 is
used when installed on Ampere or newer, SDPA otherwise. Override any of it with
`--quantization`, `--batch-size`, `--grad-accum`, `--epochs`, `--learning-rate`,
`--lora-r`, `--neftune`.

Assistant response tokens alone contribute loss; prompts and padding are masked.
Each sequence is composed as (inference prefix from `apply_chat_template` with
`add_generation_prompt=True`) + (completion tokens) + (end-of-turn token), so the
trained prefix matches the served one by construction rather than by assertion —
an earlier version asserted the two renderings matched and fired on valid data,
because Qwen3's template inserts generation-time scaffolding the full rendering
does not reproduce. Overlength examples are excluded and counted in
`tokenization_report.json`, never silently truncated. The test split is not used
by training.

### Library versions

`requirements-train.txt` pins `transformers==4.57.1`. The recipe also runs on
transformers 5.x: of the 23 `TrainingArguments` fields it uses, only
`warmup_ratio` was removed, so the trainer computes `warmup_steps` itself.
`Trainer(processing_class=...)` exists in both. If you upgrade and hit a
`TypeError` on an unexpected keyword argument, that is the class of problem.

### Measured run

First successful run, recorded so results can be traced to a machine:

| | |
|---|---|
| GPU | NVIDIA RTX A6000, 47 GiB |
| quantization | none (bf16) |
| attention | SDPA |
| batch | 4 × 4 accumulation (effective 16) |
| wall clock | 865 s for 3 epochs |
| final train loss | 1.939 |
| validation loss | epoch 1 — 1.9353 · **epoch 2 — 1.8994** · epoch 3 — 1.9225 |

Validation loss turned up after epoch 2, so **epoch 2 (`checkpoint-102`) is the
adapter to use** and 3 epochs is one too many for this dataset size. `train.py`
loads the best checkpoint at the end and writes it to
`training/checkpoints/brand-qwen/adapter/`, so the saved adapter is already the
epoch-2 one — but verify before merging, because `--epochs` changes which
checkpoint that is.

A successful preparation run is not a successful training run; no adapter exists
until GPU training completes.

## Exporting the adapter

vLLM can serve the adapter without merging, which is what
[`serving/README.md`](../serving/README.md) does — it keeps the base model
available for signal ranking on the same GPU. Merge only when you need a single
set of weights:

```sh
python training/merge_adapter.py \
    --adapter training/checkpoints/brand-qwen/adapter \
    --output  training/checkpoints/brand-qwen/merged
```

Merging is required for GGUF conversion (llama.cpp, Ollama) and removes the
adapter as a moving part at demo time. It runs on CPU if no GPU is free, needing
roughly 16 GB of RAM for a 4B. Merging a 4-bit-trained adapter into bf16 weights
is standard and slightly lossy. The output directory holds `merge_info.json`
recording which checkpoint went in — check it rather than assuming.

Do not point vLLM's `--lora-modules` at merged weights: it needs a directory
containing `adapter_config.json`, and applying the adapter on top of weights that
already contain it degrades output without erroring. `--max-lora-rank` must be at
least `--lora-r` (16 by default).

## Serving and backend integration

See **[`serving/README.md`](../serving/README.md)** for the runbook: the Slurm
job script, the SSH tunnel, the environment variables, and the failure modes
worth knowing before a demo. In short:

```sh
sbatch serving/serve_nexus.sbatch     # on a Nexus login node
./serving/tunnel.sh                   # on your laptop, VPN connected
```

```dotenv
GENERATION_BASE_URL=http://localhost:39109/v1
GENERATION_MODEL=wavelength
```

`llm.call_generation` sends drafts to this endpoint when configured; failures are
reported rather than silently switching away from the tuned model. With both
settings blank, drafts use the existing provider configuration. Signal ranking
continues through `llm.call_llm` and its provider chain, so ranking and generation
can point at different models — which is the point of serving the adapter as a
LoRA module rather than merged weights. The `/chat` route also retains its
existing provider configuration; the adapter is for draft generation.

The adapter does not become available through Hugging Face Inference Providers
merely by uploading it.

## Regional retrieval (RAG)

Run extraction, table conversion and cleaning as described in `data/README.md`,
then load both weather snapshots and cleaned candidates:

```sh
python data/pipeline/load_mongo.py
python data/pipeline/load_candidates.py
```

The state snapshot reader supplies recent weather. The cleaned candidate collection
supplies trends, news, events, calendar, social, sports, Wikipedia attention and
YouTube. Candidate retrieval filters state/national scope, freshness, duplicates,
noise and sensitivity, then balances source quotas. Ranking selects up to three
relevant signals with scores >=5; an empty choice or ranker failure supplies no
hooks. All sources are eligible, not all are forced into every response.

Only selected signals reach the generation prompt, with national and guessed
geography identified. Weather is optional supporting context. Unranked source
payloads and the old fallback search trends are no longer appended to draft prompts.
The saved audit includes the full candidate pool, scores, selected items and
refusals; these are model judgments, not human-reviewed ranker labels.

Freshness is load-bearing and currently unmet. Generation does not fetch external
sources on demand, there is no scheduled extract, and a snapshot older than
`LOOKBACK_DAYS` (default 2, overridable with `SIGNAL_LOOKBACK_DAYS`) yields an
empty pool and ungrounded drafts for every state. Re-run the extract before any
evaluation or demo, and report the `stale_days` the audit records.

## Not yet done

Stated plainly so nobody reports these as finished:

- **No base-vs-adapter comparison.** The three-way run — base zero-shot, base
  with few-shot retrieval, adapter — has not happened. Validation loss alone does
  not establish the adapter is better for the product's actual task.
- **No ranker precision@3.** The 290 human-labelled retrieval rows exist, but
  every scored run so far fell back to `fallback:no-llm` or an unreachable
  provider, so the headline retrieval number is still unmeasured.
- **No inter-annotator agreement.** `overlap.csv` has not been labelled by a
  second reviewer, so the 290 labels have no Cohen's κ and no ceiling to be read
  against. They are model-proposed, human-reviewed, zero overrides.
- **Two known safety-gate defects.** `tribute` and `memorial` caused 12 false
  refusals in the labelled set; `murdered`, `killer`, `rapist`, `violence`,
  `ballots`, `voter` and `politics` were missed. Gate precision measured 66.7%.
  `services/trend_service.py` has no test file.