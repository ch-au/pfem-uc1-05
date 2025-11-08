#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

LOG_FILE="./logs/server.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Load .env file safely
if [[ -f .env ]]; then
  set -a  # automatically export all variables
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "[start] Using host=${HOST:-0.0.0.0} port=${PORT:-8000}"
echo "[start] Logs: $LOG_FILE"

HOST_ARG=${HOST:-0.0.0.0}
PORT_ARG=${PORT:-8000}

exec python3 run.py --host "$HOST_ARG" --port "$PORT_ARG" --reload --log-file "$LOG_FILE"




