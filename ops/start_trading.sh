#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${TRADING_RUNTIME_DIR:-${HOME}/trading/Trading-runtime}"
BACKEND_PORT="${TRADING_BACKEND_PORT:-8020}"
FRONTEND_PORT="${TRADING_FRONTEND_PORT:-5180}"
NODE_BIN="${TRADING_NODE_BIN:-${HOME}/.hermes/node/bin/node}"

if [ ! -x "$NODE_BIN" ]; then
  NODE_BIN="$(command -v node || true)"
fi
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
  echo "Node runtime not found for frontend" >&2
  exit 1
fi

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

worker_healthy() {
  local pid_file="$RUNTIME/pids/shadow-worker.pid"
  local heartbeat="$RUNTIME/shadow/worker_heartbeat.json"

  pid_alive "$pid_file" || return 1
  [ -f "$heartbeat" ] || return 1
  grep -q '"ok": true' "$heartbeat" || return 1

  local now mtime age
  now="$(date +%s)"
  mtime="$(stat -c %Y "$heartbeat" 2>/dev/null || echo 0)"
  age=$((now - mtime))
  [ "$age" -le 180 ]
}

if ! port_listening "$BACKEND_PORT"; then
  (
    exec 9>&-
    cd "$BASE/backend"
    nohup .venv/bin/uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "$BACKEND_PORT" \
      >>"$RUNTIME/logs/backend.log" 2>&1 &
    echo $! >"$RUNTIME/pids/backend.pid"
  )
fi

if ! worker_healthy; then
  if pid_alive "$RUNTIME/pids/shadow-worker.pid"; then
    kill "$(cat "$RUNTIME/pids/shadow-worker.pid")" 2>/dev/null || true
    sleep 1
  fi
  (
    exec 9>&-
    cd "$BASE/backend"
    nohup .venv/bin/python -m app.shadow_worker \
      >>"$RUNTIME/logs/shadow-worker.log" 2>&1 &
    echo $! >"$RUNTIME/pids/shadow-worker.pid"
  )
fi

if ! port_listening "$FRONTEND_PORT"; then
  (
    exec 9>&-
    cd "$BASE/frontend"
    nohup "$NODE_BIN" ./node_modules/vite/bin/vite.js \
      --host 0.0.0.0 \
      --port "$FRONTEND_PORT" \
      >>"$RUNTIME/logs/frontend.log" 2>&1 &
    echo $! >"$RUNTIME/pids/frontend.pid"
  )
fi


if port_listening "$BACKEND_PORT"; then
  curl -fsS --max-time 3     "http://127.0.0.1:$BACKEND_PORT/api/v1/session/preflight"     >>"$RUNTIME/logs/session-preflight.jsonl" 2>/dev/null     && printf '\n' >>"$RUNTIME/logs/session-preflight.jsonl"     || true
fi
