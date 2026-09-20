#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${TRADING_RUNTIME_DIR:-${HOME}/trading/Trading-runtime}"
BACKEND_PORT="${TRADING_BACKEND_PORT:-8020}"
FRONTEND_PORT="${TRADING_FRONTEND_PORT:-5180}"

mkdir -p "$RUNTIME/logs" "$RUNTIME/pids" "$RUNTIME/shadow"
exec 9>"$RUNTIME/start.lock"
flock -n 9 || exit 0

export TRADING_SHADOW_LEDGER_DIR="${TRADING_SHADOW_LEDGER_DIR:-$RUNTIME/shadow}"
export TRADING_MACRO_EVENTS_PATH="${TRADING_MACRO_EVENTS_PATH:-$RUNTIME/macro_events.json}"

port_listening() {
  ss -ltn "( sport = :$1 )" | grep -q LISTEN
}

pid_alive() {
  local file="$1"
  [ -f "$file" ] || return 1
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

if ! port_listening "$BACKEND_PORT"; then
  (
    cd "$BASE/backend"
    nohup .venv/bin/uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "$BACKEND_PORT" \
      >>"$RUNTIME/logs/backend.log" 2>&1 &
    echo $! >"$RUNTIME/pids/backend.pid"
  )
fi

if ! pid_alive "$RUNTIME/pids/shadow-worker.pid"; then
  (
    cd "$BASE/backend"
    nohup .venv/bin/python -m app.shadow_worker \
      >>"$RUNTIME/logs/shadow-worker.log" 2>&1 &
    echo $! >"$RUNTIME/pids/shadow-worker.pid"
  )
fi

if ! port_listening "$FRONTEND_PORT"; then
  (
    cd "$BASE/frontend"
    nohup node ./node_modules/vite/bin/vite.js \
      --host 0.0.0.0 \
      --port "$FRONTEND_PORT" \
      >>"$RUNTIME/logs/frontend.log" 2>&1 &
    echo $! >"$RUNTIME/pids/frontend.pid"
  )
fi
