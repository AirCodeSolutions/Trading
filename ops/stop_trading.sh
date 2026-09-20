#!/usr/bin/env bash
set -euo pipefail

RUNTIME="${TRADING_RUNTIME_DIR:-${HOME}/trading/Trading-runtime}"

stop_pid() {
  local name="$1"
  local file="$RUNTIME/pids/$name.pid"
  [ -f "$file" ] || return 0

  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
}

stop_pid backend
stop_pid shadow-worker
stop_pid frontend
