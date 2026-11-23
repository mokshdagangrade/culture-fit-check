#!/bin/bash
# Serve the base model plus the brand LoRA adapter on one Nexus GPU, as an
# OpenAI-compatible endpoint the backend can reach through an SSH tunnel.
#
#   sbatch serving/serve_nexus.sbatch
#   head serve-<jobid>.out        # prints the exact tunnel command
#
# Batch, not srun: the job survives a closed laptop and a dropped SSH session.
#SBATCH --job-name=wavelength-serve
#SBATCH --account=nexus
#SBATCH --partition=tron
#SBATCH --qos=default
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=serve-%j.out

set -euo pipefail

# ---- configuration (override by exporting before sbatch) --------------------
PORT="${WAVELENGTH_PORT:-39109}"
BASE_MODEL="${WAVELENGTH_BASE_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
ADAPTER="${WAVELENGTH_ADAPTER:-$HOME/culture-fit/training/checkpoints/brand-qwen/adapter}"
CONDA_ENV="${WAVELENGTH_CONDA_ENV:-RMMAU}"
LOGIN_HOST="${WAVELENGTH_LOGIN_HOST:-nexuscsd00.umiacs.umd.edu}"
MAX_MODEL_LEN="${WAVELENGTH_MAX_MODEL_LEN:-4096}"

# Keep the HF cache off the small home quota.
export HF_HOME="${HF_HOME:-/fs/nexus-scratch/$USER/hf}"

# FlashInfer JIT-compiles its top-k/top-p kernel on the first *random* sample
# and needs nvcc, which lives in a module on Nexus rather than /usr/local/cuda.
# Without this the engine dies on the first temperature>0 request -- which is
# every real draft, while a greedy health check passes. See serving/README.md.
export VLLM_USE_FLASHINFER_SAMPLER=0

# ---- environment -----------------------------------------------------------
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

if [ ! -f "$ADAPTER/adapter_config.json" ]; then
  echo "ERROR: no adapter_config.json under $ADAPTER" >&2
  echo "       --lora-modules needs the adapter directory, not merged weights." >&2
  exit 1
fi

# ---- what the operator needs, at the top of the log ------------------------
NODE="$(hostname -f)"
echo "================================================================"
echo "node        : $NODE"
echo "port        : $PORT"
echo "base model  : $BASE_MODEL"
echo "adapter     : $ADAPTER"
echo "slurm job   : ${SLURM_JOB_ID:-none}"
echo
echo "tunnel (run on your laptop, leave it running):"
echo "  ssh -N -L $PORT:$NODE:$PORT $USER@$LOGIN_HOST"
echo "================================================================"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
echo

# ---- readiness probe, so the log says when it is actually usable -----------
(
  for _ in $(seq 1 120); do
    sleep 5
    if curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; then
      echo "READY: served models ->"
      curl -s "http://localhost:$PORT/v1/models" \
        | python -c 'import json,sys; [print("  "+m["id"]) for m in json.load(sys.stdin)["data"]]' \
        2>/dev/null || true
      echo "READY: ssh -N -L $PORT:$NODE:$PORT $USER@$LOGIN_HOST"
      exit 0
    fi
  done
  echo "WARNING: server did not answer /v1/models within 10 minutes"
) &

# ---- serve -----------------------------------------------------------------
# --max-lora-rank must be >= the adapter's r (train.py uses --lora-r 16).
# --enforce-eager skips torch.compile, which also wants nvcc at startup.
exec vllm serve "$BASE_MODEL" \
  --served-model-name qwen3-4b-base \
  --enable-lora \
  --lora-modules "wavelength=$ADAPTER" \
  --max-lora-rank 16 \
  --host 0.0.0.0 --port "$PORT" \
  --max-model-len "$MAX_MODEL_LEN" \
  --gpu-memory-utilization 0.90 \
  --enforce-eager
