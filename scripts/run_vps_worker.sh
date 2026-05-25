#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOOP_SECONDS="${LOOP_SECONDS:-10}"

if ! [[ "$LOOP_SECONDS" =~ ^[0-9]+$ ]] || [ "$LOOP_SECONDS" -lt 5 ]; then
  LOOP_SECONDS=10
fi

cd "$ROOT_DIR"

unset TELEGRAM_SMOKE_TEST

if [ -f .env ]; then
  sed -i '/^TELEGRAM_SMOKE_TEST=/d' .env
fi

while true; do
  HISTORY_BACKUP="$(mktemp)"
  HISTORY_PRESENT=0
  if [ -f data/history.json ]; then
    cp data/history.json "$HISTORY_BACKUP"
    HISTORY_PRESENT=1
  fi

  rm -f data/history.json
  git pull --ff-only

  if [ "$HISTORY_PRESENT" -eq 1 ] && [ -f "$HISTORY_BACKUP" ]; then
    mv "$HISTORY_BACKUP" data/history.json
  fi

  . .venv/bin/activate
  python3 bot.py
  sleep "$LOOP_SECONDS"
done