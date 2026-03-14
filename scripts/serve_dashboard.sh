#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"
REPORTS_DIR="$PROJECT_DIR/reports"
PORT=8080
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

cd "$REPORTS_DIR"
exec "$PYTHON_BIN" -m http.server "$PORT" --bind 0.0.0.0
