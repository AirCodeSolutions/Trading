#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${TRADING_RUNTIME_DIR:-${HOME}/trading/Trading-runtime}"
TAG="trading_new_autostart"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

mkdir -p "$RUNTIME/logs"

(crontab -l 2>/dev/null || true)   | grep -v "$TAG"   >"$TMP"

cat >>"$TMP" <<EOF
@reboot sleep 20 && bash $BASE/ops/start_trading.sh >> $RUNTIME/logs/autostart.log 2>&1 # $TAG
*/5 * * * * bash $BASE/ops/start_trading.sh >> $RUNTIME/logs/watchdog.log 2>&1 # $TAG
EOF

crontab "$TMP"
echo "Trading autostart installed for $BASE"
