#!/bin/bash
# Open the SSH tunnel to whichever node the serve job landed on.
#
#   ./serving/tunnel.sh
#
# Run this on your laptop, with the VPN connected. It reads the node from
# Slurm instead of you typing it, because the node changes every allocation
# and a wrong hostname fails as an empty reply rather than a clear error.
set -euo pipefail

PORT="${WAVELENGTH_PORT:-39109}"
LOGIN_HOST="${WAVELENGTH_LOGIN_HOST:-nexuscsd00.umiacs.umd.edu}"
REMOTE_USER="${WAVELENGTH_USER:-$USER}"
JOB_NAME="${WAVELENGTH_JOB_NAME:-wavelength-serve}"

echo "Looking up the running $JOB_NAME job on $LOGIN_HOST ..."
NODE="$(ssh "$REMOTE_USER@$LOGIN_HOST" \
  "squeue -u $REMOTE_USER -n $JOB_NAME -h -t RUNNING -o %N" | head -1 | tr -d '[:space:]')"

if [ -z "$NODE" ]; then
  echo "ERROR: no RUNNING job named $JOB_NAME." >&2
  echo "       sbatch serving/serve_nexus.sbatch   then wait for it to start." >&2
  exit 1
fi

# A stale tunnel owns the local port and silently forwards to a dead node.
if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Closing an existing listener on $PORT ..."
  pkill -f "ssh -N -L $PORT:" || true
  sleep 1
fi

FQDN="$NODE"
case "$NODE" in *.*) ;; *) FQDN="$NODE.umiacs.umd.edu" ;; esac

echo "Forwarding localhost:$PORT -> $FQDN:$PORT (ctrl-c to stop)"
echo "Verify in another terminal: curl -s localhost:$PORT/v1/models"
exec ssh -N -L "$PORT:$FQDN:$PORT" "$REMOTE_USER@$LOGIN_HOST"