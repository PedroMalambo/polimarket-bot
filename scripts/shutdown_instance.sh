#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/projects/polymarket-bot"
SESSION_NAME="polymarket-bot"

echo "Checking bot status before shutdown..."

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "ERROR: Bot is still running in tmux session: $SESSION_NAME"
  echo "Stop the bot first with: ./scripts/stop_bot.sh"
  exit 1
fi

echo "Bot is not running."
echo "Syncing filesystem..."
sync

echo "Shutdown command prepared."
echo "To power off now, run:"
echo "sudo shutdown -h now"
