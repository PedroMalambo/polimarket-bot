#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"
SESSION_NAME="polymarket-bot"
PID_FILE="$PROJECT_DIR/runtime/bot.pid"
LOCK_FILE="$PROJECT_DIR/runtime/bot.lock"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
  echo "Bot stopped: $SESSION_NAME"
else
  echo "Session $SESSION_NAME not running."
fi

rm -f "$PID_FILE" "$LOCK_FILE"

echo "Cleaned runtime files."
