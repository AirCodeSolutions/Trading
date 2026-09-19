#!/usr/bin/env bash
set -euo pipefail

TAG="trading_new_autostart"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

(crontab -l 2>/dev/null || true)   | grep -v "$TAG"   >"$TMP"
crontab "$TMP"
echo "Trading autostart removed"
