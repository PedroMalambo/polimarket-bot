#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"
SESSION_NAME="polymarket-bot"
PID_FILE="$PROJECT_DIR/runtime/bot.pid"
LOCK_FILE="$PROJECT_DIR/runtime/bot.lock"

cd "$PROJECT_DIR"

mkdir -p runtime

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Session $SESSION_NAME already exists."
  exit 0
fi

if [ -f "$LOCK_FILE" ]; then
  echo "Lock file exists: $LOCK_FILE"
  echo "Refusing to start bot."
  exit 1
fi

touch "$LOCK_FILE"

tmux new-session -d -s "$SESSION_NAME" "cd $PROJECT_DIR && source .venv/bin/activate && echo \$\$ > $PID_FILE && python run_bot.py"

sleep 1

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Bot started in tmux session: $SESSION_NAME"
  echo "PID_FILE=$PID_FILE"
  echo "LOCK_FILE=$LOCK_FILE"
else
  rm -f "$LOCK_FILE"
  echo "Failed to start bot."
  exit 1
fi
