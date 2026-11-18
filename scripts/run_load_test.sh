#!/usr/bin/env bash
# Sobe a API (SQLite em arquivo), executa o Locust com 50 usuários simultâneos
# e derruba o servidor ao final. Uso: scripts/run_load_test.sh [duração] [usuários]
set -euo pipefail

DURATION="${1:-30s}"
USERS="${2:-50}"
PORT="${PORT:-8000}"
HOST="http://127.0.0.1:${PORT}"
DB_FILE="$(mktemp -d)/wallet-load.db"
mkdir -p reports/load

DATABASE_PATH="$DB_FILE" PYTHONPATH=src \
  python -m uvicorn wallet.main:app --port "$PORT" --log-level warning \
  > reports/load/server.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 50); do
  curl -fs "$HOST/health" > /dev/null && break
  sleep 0.2
done

locust -f load/locustfile.py --headless \
  -u "$USERS" -r "$USERS" -t "$DURATION" --host "$HOST" \
  --csv reports/load/locust --html reports/load/locust-report.html \
  --only-summary 2>&1 | tee reports/load/locust.log
