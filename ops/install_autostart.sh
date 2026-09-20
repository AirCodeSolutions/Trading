#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="\${TRADING_RUNTIME_DIR:-\${HOME}/trading/Trading-runtime}"
TAG="trading_new_autostart"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

mkdir -p "$RUNTIME/logs" "$RUNTIME/shadow"

if [ ! -f "$RUNTIME/macro_events.json" ]; then
  cp "$BASE/backend/config/macro_events_2026.json" "$RUNTIME/macro_events.json"
fi

(
  cd "$BASE/backend"
  .venv/bin/python scripts/sync_macro_calendar.py \
    --base config/macro_events_2026.json \
    --output "$RUNTIME/macro_events.json"
) >>"$RUNTIME/logs/macro-sync.log" 2>&1 || true

if [ -n "\${TRADING_MT4_FILES_DIR:-}" ]; then
  (
    cd "$BASE/backend"
    .venv/bin/python scripts/refresh_research_admissions.py \
      --files-dir "$TRADING_MT4_FILES_DIR" \
      --runtime-dir "$RUNTIME/shadow" \
      --timezone "\${TRADING_MT4_SERVER_TIMEZONE:-Europe/Athens}"
  ) >>"$RUNTIME/logs/research-admission.log" 2>&1 || true
fi

(crontab -l 2>/dev/null || true) \
  | awk -v tag="$TAG" 'index($0, tag) == 0' \
  >"$TMP"

cat >>"$TMP" <<EOF
@reboot sleep 20 && bash $BASE/ops/start_trading.sh >> $RUNTIME/logs/autostart.log 2>&1 # $TAG
*/5 * * * * bash $BASE/ops/start_trading.sh >> $RUNTIME/logs/watchdog.log 2>&1 # $TAG
17 5 * * * cd $BASE/backend && .venv/bin/python scripts/sync_macro_calendar.py --base config/macro_events_2026.json --output $RUNTIME/macro_events.json >> $RUNTIME/logs/macro-sync.log 2>&1 # $TAG
43 5 * * * cd $BASE/backend && .venv/bin/python scripts/refresh_research_admissions.py --files-dir "$TRADING_MT4_FILES_DIR" --runtime-dir $RUNTIME/shadow --timezone "\${TRADING_MT4_SERVER_TIMEZONE:-Europe/Athens}" >> $RUNTIME/logs/research-admission.log 2>&1 # $TAG
EOF

crontab "$TMP"
echo "Trading autostart, macro sync and research refresh installed for $BASE"
