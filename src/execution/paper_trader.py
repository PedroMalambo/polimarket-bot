from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from src.portfolio.ledger_store import (
    ensure_ledger_files,
    find_open_position_by_market_id,
    load_positions,
    load_trades,
    save_positions,
    save_trades,
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def open_paper_position(simulated_entry: dict) -> dict:
    ensure_ledger_files()

    existing_open = find_open_position_by_market_id(simulated_entry["market_id"])
    if existing_open:
        return {
            "opened": False,
            "reason": "OPEN_POSITION_ALREADY_EXISTS",
            "existing_position": existing_open,
        }

    positions = load_positions()
    trades = load_trades()

    position_id = str(uuid4())
    trade_id = str(uuid4())

    position = {
        "position_id": position_id,
        "market_id": simulated_entry["market_id"],
        "question": simulated_entry["question"],
        "status": "OPEN",
        "side": "YES",
        "entry_price": simulated_entry["entry_price"],
        "current_price": simulated_entry["entry_price"],
        "max_entry_price_with_slippage": simulated_entry["max_entry_price_with_slippage"],
        "shares": simulated_entry["estimated_shares"],
        "risk_amount_usd": simulated_entry["risk_amount_usd"],
        "phase": simulated_entry["phase"],
        "stop_loss_price": simulated_entry["stop_loss_price"],
        "take_profit_price": simulated_entry["take_profit_price"],
        "score": simulated_entry.get("score"),
        "opened_at_utc": utc_now_iso(),
        "closed_at_utc": None,
        "close_reason": None,
    }

    trade = {
        "trade_id": trade_id,
        "position_id": position_id,
        "market_id": simulated_entry["market_id"],
        "question": simulated_entry["question"],
        "action": "BUY_YES_PAPER",
        "price": simulated_entry["entry_price"],
        "shares": simulated_entry["estimated_shares"],
        "notional_usd": simulated_entry["risk_amount_usd"],
        "phase": simulated_entry["phase"],
        "timestamp_utc": utc_now_iso(),
    }

    positions.append(position)
    trades.append(trade)

    save_positions(positions)
    save_trades(trades)

    return {
        "opened": True,
        "position": position,
        "trade": trade,
        "positions_count": len(positions),
        "trades_count": len(trades),
    }


def evaluate_open_positions(latest_candidates: list[dict]) -> dict:
    ensure_ledger_files()

    positions = load_positions()
    trades = load_trades()

    latest_by_market_id = {
        str(market.get("id")): market for market in latest_candidates
    }

    closed_positions: list[dict] = []

    for position in positions:
        if position.get("status") != "OPEN":
            continue

        market_id = str(position.get("market_id"))
        latest_market = latest_by_market_id.get(market_id)

        if latest_market and latest_market.get("yes_price") is not None:
            current_price = float(latest_market.get("yes_price"))
            position["current_price"] = current_price
        else:
            current_price = float(position.get("current_price", position.get("entry_price", 0.0)))

        close_reason = None
        if current_price <= float(position["stop_loss_price"]):
            close_reason = "STOP_LOSS"
        elif current_price >= float(position["take_profit_price"]):
            close_reason = "TAKE_PROFIT"

        if close_reason:
            position["status"] = "CLOSED"
            position["closed_at_utc"] = utc_now_iso()
            position["close_reason"] = close_reason
            position["current_price"] = current_price

            exit_trade = {
                "trade_id": str(uuid4()),
                "position_id": position["position_id"],
                "market_id": position["market_id"],
                "question": position["question"],
                "action": f"SELL_YES_PAPER_{close_reason}",
                "price": current_price,
                "shares": position["shares"],
                "notional_usd": round(float(position["shares"]) * current_price, 6),
                "phase": position["phase"],
                "timestamp_utc": utc_now_iso(),
            }
            trades.append(exit_trade)
            closed_positions.append(position)

    save_positions(positions)
    save_trades(trades)

    return {
        "closed_positions_count": len(closed_positions),
        "closed_positions": closed_positions,
        "positions_count": len(positions),
        "trades_count": len(trades),
    }
