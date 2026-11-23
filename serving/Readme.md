# Serving the trained model on Nexus

The backend talks to an OpenAI-compatible endpoint. In production that is a
hosted provider; for the tuned adapter it is vLLM running on a UMIACS Nexus
GPU node, reached from a laptop through an SSH tunnel.

One vLLM process serves **two** model ids:

| served id       | weights                | used by                                  |
|-----------------|------------------------|------------------------------------------|
| `qwen3-4b-base` | base Qwen3-4B-Instruct | signal ranking (`llm.call_llm`)          |
| `wavelength`    | base + brand LoRA      | draft generation (`llm.call_generation`) |

Ranking and generation are deliberately split. The adapter was trained on 809
brand-voice writing examples, and the ranker needs strict JSON over candidate
ids -- a task the adapter was not trained for and may be worse at than the base
model it came from. Serving the adapter as a LoRA module rather than merged
weights is what makes both available from one GPU.

## 1. Install vLLM in its own environment

```sh
conda create -n wavelength-serve python=3.12 -y
conda activate wavelength-serve
pip install -r serving/requirements-serve.txt
```

Do not install this into the training environment. vLLM pins its own torch.

## 2. Submit the serve job

From the repo root on a Nexus login node:

```sh
sbatch serving/serve_nexus.sbatch
squeue -u $USER -o "%A %T %N"
head -40 serve-<jobid>.out
```

The log's first lines print the node, the port, and the exact tunnel command.
Wait for `READY: served models ->` before connecting anything.

Override any default by exporting it first:

```sh
WAVELENGTH_PORT=40000 WAVELENGTH_ADAPTER=/path/to/adapter sbatch serving/serve_nexus.sbatch
```

`--gres=gpu:rtxa6000:1` is deliberate. An untyped `--gres=gpu:1` can land an
RTX 2080 Ti: 11 GB, which leaves almost no KV cache after ~8 GB of bf16 weights,
and Turing has no bf16 support at all. The A6000 (48 GB) and A4000 (16 GB) are
both Ampere and both work; the A6000 has room at 4k context.

Check the wall-time ceiling on your QoS before raising `--time`; a job asking
for more than the limit is rejected at submit rather than truncated.

## 3. Open the tunnel

On the laptop, with the VPN connected:

```sh
./serving/tunnel.sh
```

It reads the node from Slurm rather than asking you to type it, closes a stale
listener on the port first, and leaves the forward in the foreground. Verify
from a second terminal:

```sh
curl -s localhost:39109/v1/models | python3 -m json.tool
```

## 4. Point the backend at it

In `src/backend/.env`:

```dotenv
LLM_PROVIDER_CHAIN=false
LLM_BASE_URL=http://localhost:39109/v1
LLM_MODEL=qwen3-4b-base
LLM_API_KEY=local

GENERATION_BASE_URL=http://localhost:39109/v1
GENERATION_MODEL=wavelength
GENERATION_API_KEY=local
```

`.env` is read at import, so restart uvicorn -- `--reload` will not pick it up.

`LLM_PROVIDER_CHAIN=false` matters for evaluation: with the chain on, a ranker
failure falls through to Gemini or Groq and a reported precision@3 no longer
describes the model you think you measured.

Then:

```sh
cd src/backend && python check_llm.py
```

## 5. Verify the path a health check cannot reach

`check_llm.py` calls with `temperature=0`. Greedy decoding takes a different
sampler path from every real draft, so it passes on a server that will die on
the first generation request. Always also run:

```sh
curl -s localhost:39109/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"wavelength","temperature":0.8,
       "messages":[{"role":"user","content":"Write one tagline for a coffee brand in Texas."}]}'
```

This exercises the adapter and random sampling together.

## Troubleshooting

Each of these cost real time on 2026-11-23; the symptom is listed first because
that is what you will have.

**`RuntimeError: Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist`**
at startup. vLLM wheels bundle a CUDA runtime but not `nvcc`, and Nexus keeps
the toolkit in a module. `--enforce-eager` (already in the job script) skips the
`torch.compile` path that wants it. For the durable fix, match the module to the
torch build:

```sh
python -c "import torch; print(torch.version.cuda)"
module avail cuda && module load cuda/12.4
export CUDA_HOME=$(dirname "$(dirname "$(which nvcc)")")
```

**The same nvcc error mid-request, followed by `EngineDeadError` and 500s.**
Different cause, same message: FlashInfer JIT-compiles its top-k/top-p kernel at
the first *random* sample. `VLLM_USE_FLASHINFER_SAMPLER=0` (already exported by
the job script) selects the native PyTorch sampler, which compiles nothing. The
engine does not recover -- restart the job. Note that flashinfer 0.4.0 has a
reported regression where it fails to find `nvcc` even when `nvcc --version`
works, so prefer disabling the sampler over fixing the toolkit here.

**`ValueError: Loading lora <name> failed: No adapter found for <path>`.**
`--lora-modules` needs a directory containing `adapter_config.json` and
`adapter_model.safetensors`. Merged weights are not an adapter. Locate the real
one with `find ~ -name adapter_config.json`.

**`curl` returns nothing and `python3 -m json.tool` says
`Expecting value: line 1 column 1`.** An empty reply, not a refusal: something is
listening locally but cannot reach the far end. Usually a tunnel pointed at a
stale node -- or at a literal placeholder hostname. `ps -o pid,command -p $(lsof
-tiTCP:39109 -sTCP:LISTEN)` shows the target. `serving/tunnel.sh` exists to stop
this recurring.

**`channel N: open failed: connect failed: Connection refused`** in the ssh
terminal. The remote end refused, so the server is gone: check `squeue` and the
tail of the job log. An engine that died earlier produces this for every later
request.

**Drafts generate but every state reports `reason=empty-pool`.** Not a serving
problem. Either the state is outside US coverage (`regions.py`), or no snapshot
falls inside `LOOKBACK_DAYS` of today -- refresh the pipeline
(`data/pipeline/run_extract.py` then `load_candidates.py`), or set
`SIGNAL_LOOKBACK_DAYS` to reach an older snapshot and accept the `stale_days`
the audit will report.

## Known limitation

A tunnel is a demo mechanism, not a deployment. Nothing generates when the job
is not running or the VPN is down, and the node changes on every allocation.
Keep a hosted provider configured in `.sample.env` so other developers' local
runs do not depend on someone's Slurm job.