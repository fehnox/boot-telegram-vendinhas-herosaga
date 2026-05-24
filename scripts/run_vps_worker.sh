#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

while true; do
  git pull --ff-only
  . .venv/bin/activate
  python3 bot.py
  sleep 180
done