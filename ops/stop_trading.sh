#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${TRADING_RUNTIME_DIR:-${HOME}/trading/Trading-runtime}"
BACKEND_PORT="${TRADING_BACKEND_PORT:-8020}"
FRONTEND_PORT="${TRADING_FRONTEND_PORT:-5180}"

wait_for_exit() {
  local pid="$1"
  for _ in $(seq 1 50); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.1
  done
  return 1
}

stop_pid() {
  local name="$1"
  local file="$RUNTIME/pids/$name.pid"
  [ -f "$file" ] || return 0

  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    if ! wait_for_exit "$pid"; then
      echo "Refusing to continue: $name PID $pid did not stop" >&2
      exit 1
    fi
  fi
  rm -f "$file"
}

listener_pid() {
  local port="$1"
  ss -ltnp "( sport = :$port )" 2>/dev/null \
    | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' \
    | head -1
}

safe_stop_listener() {
  local name="$1"
  local port="$2"
  local expected_cwd="$3"
  local expected_fragment="$4"
  local pid
  pid="$(listener_pid "$port")"
  [ -n "$pid" ] || return 0

  local cwd cmd
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  if [ "$cwd" != "$expected_cwd" ] || [[ "$cmd" != *"$expected_fragment"* ]]; then
    echo "Refusing to stop unexpected $name listener on port $port: PID $pid cwd=$cwd cmd=$cmd" >&2
    exit 1
  fi

  echo "Stopping orphaned $name listener PID $pid on port $port" >&2
  kill "$pid" 2>/dev/null || true
  if ! wait_for_exit "$pid"; then
    echo "Refusing to continue: orphaned $name PID $pid did not stop" >&2
    exit 1
  fi
}

safe_stop_worker() {
  local expected_cwd="$1"
  local pid cwd cmd exe exe_name
  while read -r pid; do
    [ -n "$pid" ] || continue
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
    exe_name="$(basename "$exe" 2>/dev/null || true)"
    if (
      [ "$cwd" = "$expected_cwd" ]       && [[ "$exe_name" == python* ]]       && [[ "$cmd" == *"-m app.shadow_worker"* ]]
    ); then
      echo "Stopping orphaned shadow worker PID $pid" >&2
      kill "$pid" 2>/dev/null || true
      if ! wait_for_exit "$pid"; then
        echo "Refusing to continue: orphaned shadow worker PID $pid did not stop" >&2
        exit 1
      fi
    fi
  done < <(pgrep -f "app.shadow_worker" || true)
}

stop_pid backend
stop_pid shadow-worker
stop_pid frontend

# PID files are advisory. A crashed deployment step can remove or stale a PID
# file while the process keeps serving. Clean up only processes that are both
# owned by this repo (cwd check) and match the expected Trading command.
safe_stop_listener backend "$BACKEND_PORT" "$BASE/backend" "uvicorn app.main:app"
safe_stop_worker "$BASE/backend"
safe_stop_listener frontend "$FRONTEND_PORT" "$BASE/frontend" "vite/bin/vite.js"
