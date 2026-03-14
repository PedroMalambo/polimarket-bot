from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path


RUNTIME_DIR = Path("data/runtime")
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

DAILY_SUMMARY_STATE_FILE = RUNTIME_DIR / "daily_summary_state.json"


def utc_today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def load_daily_summary_state() -> dict:
    if not DAILY_SUMMARY_STATE_FILE.exists():
        return {}

    try:
        return json.loads(DAILY_SUMMARY_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_daily_summary_state(payload: dict) -> None:
    DAILY_SUMMARY_STATE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def should_send_daily_summary() -> bool:
    state = load_daily_summary_state()
    last_sent_date = state.get("last_sent_utc_date")
    return last_sent_date != utc_today_str()


def mark_daily_summary_sent() -> None:
    save_daily_summary_state(
        {
            "last_sent_utc_date": utc_today_str(),
            "last_sent_at_utc": datetime.now(UTC).isoformat(),
        }
    )


def build_daily_summary_message(account_state: dict, kill_switch_triggered: bool) -> str:
    return (
        "📘 DAILY BOT SUMMARY\n"
        f"UTC Date: {utc_today_str()}\n"
        f"Cash Available: {account_state['cash_available']}\n"
        f"Capital Committed: {account_state['capital_committed']}\n"
        f"Open Market Value: {account_state['open_market_value']}\n"
        f"Realized PnL: {account_state['realized_pnl']}\n"
        f"Unrealized PnL: {account_state['unrealized_pnl']}\n"
        f"Equity Estimate: {account_state['equity_estimate']}\n"
        f"Open Positions: {account_state['open_positions_count']}\n"
        f"Closed Positions: {account_state['closed_positions_count']}\n"
        f"Kill Switch Triggered: {kill_switch_triggered}"
    )
