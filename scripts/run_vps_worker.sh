#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOOP_SECONDS="${LOOP_SECONDS:-30}"

if ! [[ "$LOOP_SECONDS" =~ ^[0-9]+$ ]] || [ "$LOOP_SECONDS" -lt 5 ]; then
  LOOP_SECONDS=30
fi

cd "$ROOT_DIR"

while true; do
  git pull --ff-only
  . .venv/bin/activate
  python3 bot.py
  sleep "$LOOP_SECONDS"
done