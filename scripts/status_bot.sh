#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"
SESSION_NAME="polymarket-bot"
PID_FILE="$PROJECT_DIR/runtime/bot.pid"
LOCK_FILE="$PROJECT_DIR/runtime/bot.lock"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "STATUS=RUNNING"
  echo "SESSION_NAME=$SESSION_NAME"
  tmux list-windows -t "$SESSION_NAME"

  if [ -f "$PID_FILE" ]; then
    echo "PID_FILE_PRESENT=yes"
    echo "PID=$(cat "$PID_FILE")"
  else
    echo "PID_FILE_PRESENT=no"
  fi

  if [ -f "$LOCK_FILE" ]; then
    echo "LOCK_FILE_PRESENT=yes"
  else
    echo "LOCK_FILE_PRESENT=no"
  fi
else
  echo "STATUS=STOPPED"

  if [ -f "$PID_FILE" ]; then
    echo "PID_FILE_PRESENT=yes"
  else
    echo "PID_FILE_PRESENT=no"
  fi

  if [ -f "$LOCK_FILE" ]; then
    echo "LOCK_FILE_PRESENT=yes"
  else
    echo "LOCK_FILE_PRESENT=no"
  fi
fi

echo
echo "LAST_LOG_LINES:"
tail -n 20 "$PROJECT_DIR/logs/app.log" 2>/dev/null || true
