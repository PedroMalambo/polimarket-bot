#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"

cd "$PROJECT_DIR"
mkdir -p runtime logs

source .venv/bin/activate
exec python run_bot.py
