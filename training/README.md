# Marketing generator training data

## Ranker review export and regression tests

From the repository root, use an existing backend environment or create one:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r src/backend/requirements.txt
python -m unittest discover -s training -p 'test_*.py' -v
PYTHONPATH=src/backend python -c 'import fastapi, unittest; unittest.main(module=None)' test_backend test_generation test_projects -v
```

These tests mock model and database calls; they need no API keys, MongoDB server,
GPU, or training datasets. FastAPI is loaded before the backend tests because
their existing `sys.modules` patches otherwise reload its exception class.
The older `test_api.py` targets retired endpoints and is not part of this command.

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

## Generator training

Run from the repository root in a separate training environment:

```sh
python -m pip install -r training/requirements.txt
python training/prepare_data.py
python -m unittest discover -s training -p 'test_*.py' -v
```

PyArrow 19 failed to read these files with `Repetition level histogram size
mismatch`; PyArrow 26 successfully reads them. Backend dependencies are unchanged.

The preparation command writes ignored artifacts under `training/out/`:

- `train.jsonl`, `validation.jsonl`, `test.jsonl`: system/user/assistant messages.
- Matching `*.manifest.jsonl` files: source rows, brand, normalized prompt and
  completion hashes for auditing. Do not pass manifests to the trainer.
- `report.json`: input checksums, exclusions, split sizes and completion lengths.

Defaults use `brandvoice_briefs` writing tasks with brand reference fields and
the enhanced prompt/completion pair from `marketing_instruct`. The original
and enhanced variants are never both included. Use `--marketing-variant original`
to select original pairs instead; missing completions are excluded. The 296
marketing principles are excluded unless `--include-principles` is specified.
No completion is fabricated for a missing target.

Splits target 80/10/10 by source with seed 42. Connected groups of repeated
normalized prompts, repeated normalized completions, and the same brand remain
together, including connections across datasets. Brand holdout measures transfer
to unseen brands. Group sizes can shift the proportions. This is exact normalized
deduplication, not semantic paraphrase detection or campaign-family detection;
review those before treating evaluation results as independent.

## Before running model training

The prepared files are training inputs, not a trained model. These datasets teach
marketing writing and brand conditioning; they do not supply regional-fit scores
or brand/signal relevance labels for the ranker. Keep live trends in retrieval.

Review dataset provenance and usage terms, sample targets for unsupported claims,
and check overlap or paraphrases across sources. Some examples ask for frameworks
and explanations, while the app usually asks for finished copy; evaluate that
behavior explicitly. The instruction corpus outnumbers brand examples by about
8:1, so compare brand-focused training with mixed training on held-out brand tasks.

## Selected model and training

Use [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
a 4B instruction model under Apache 2.0. It is already the configured HF model
in this repository. Fine-tune brand writing with QLoRA; keep live regional facts
in retrieval rather than model weights. This is an initial baseline, not a claim
that it outperforms the current hosted providers.

The training recipe targets a single NVIDIA GPU on Linux. Start with a 16–24 GB
GPU as a planning estimate, not a measured requirement. The Mac workspace has not
run GPU training. Install and run in a separate Python 3.11 environment on that host:

```sh
python -m pip install -r training/requirements-train.txt
python training/prepare_data.py
python training/train.py --max-steps 2 --output-dir training/checkpoints/smoke
python training/train.py
```

Training defaults: 2 epochs, learning rate 1e-4, LoRA rank 16/alpha 32, 4-bit NF4,
2048 token context, batch 1 with 16 accumulation steps. Assistant response tokens
alone contribute loss; prompts and padding are masked. The native chat template
must produce a matching inference prefix. Overlength examples are excluded and
counted in `tokenization_report.json`, never silently truncated. The test split
is not used by training. Tune configuration on validation, and compare base and
adapter on held-out test tasks before enabling it in production.

The recipe saves the best validation-loss adapter under
`training/checkpoints/brand-qwen/adapter/`. A successful preparation run is not a
successful training run; no adapter exists until GPU training completes. Training
and serving dependencies have not been integration-tested on a GPU here.

## Serving and backend integration

On a Linux GPU server with vLLM installed in its own environment, from the repo root:

```sh
vllm serve Qwen/Qwen3-4B-Instruct-2507 --port 8001 --enable-lora \
  --lora-modules wavelength-brand=training/checkpoints/brand-qwen/adapter \
  --max-model-len 8192
```

[vLLM supports serving LoRA adapters by model name](https://docs.vllm.ai/en/latest/features/lora/).
Set in `src/backend/.env` after the adapter server is ready, then restart the backend:

```dotenv
GENERATION_BASE_URL=http://localhost:8001/v1
GENERATION_MODEL=wavelength-brand
GENERATION_API_KEY=
```

Use the reachable server URL if it runs on another machine. Set the API key when
server authentication is enabled. The adapter does not automatically become
available through Hugging Face Inference Providers merely by uploading it.

`llm.call_generation` sends drafts to this endpoint when configured; failures are
reported rather than silently switching away from the tuned model. With both
settings blank, drafts use the existing provider configuration. Signal ranking
continues through `llm.call_llm` and its existing provider chain. The `/chat` route
also retains its existing provider configuration; the adapter is for draft generation.

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
refusals; these are model judgments, not human-reviewed ranker labels. Refresh the
pipeline regularly: generation does not fetch external sources on demand.
