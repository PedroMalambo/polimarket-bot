from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from src.config.settings import get_settings
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


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def get_latest_trade_for_market(market_id: str) -> dict | None:
    trades = load_trades()
    market_trades = [t for t in trades if str(t.get("market_id")) == str(market_id)]

    if not market_trades:
        return None

    market_trades.sort(key=lambda t: t.get("timestamp_utc", ""))
    return market_trades[-1]


def is_market_in_cooldown(market_id: str, cooldown_minutes: int) -> tuple[bool, dict | None, float | None]:
    latest_trade = get_latest_trade_for_market(market_id)
    if not latest_trade:
        return False, None, None

    timestamp_utc = latest_trade.get("timestamp_utc")
    if not timestamp_utc:
        return False, latest_trade, None

    latest_trade_dt = parse_iso_datetime(timestamp_utc)
    now_dt = datetime.now(UTC)
    elapsed_seconds = (now_dt - latest_trade_dt).total_seconds()
    elapsed_minutes = elapsed_seconds / 60

    if elapsed_minutes < cooldown_minutes:
        return True, latest_trade, round(elapsed_minutes, 2)

    return False, latest_trade, round(elapsed_minutes, 2)


def open_paper_position(simulated_entry: dict) -> dict:
    ensure_ledger_files()
    settings = get_settings()

    existing_open = find_open_position_by_market_id(simulated_entry["market_id"])
    if existing_open:
        return {
            "opened": False,
            "reason": "OPEN_POSITION_ALREADY_EXISTS",
            "existing_position": existing_open,
        }

    in_cooldown, latest_trade, elapsed_minutes = is_market_in_cooldown(
        market_id=simulated_entry["market_id"],
        cooldown_minutes=settings.MARKET_COOLDOWN_MINUTES,
    )
    if in_cooldown:
        return {
            "opened": False,
            "reason": "MARKET_COOLDOWN_ACTIVE",
            "latest_trade": latest_trade,
            "elapsed_minutes": elapsed_minutes,
            "cooldown_minutes": settings.MARKET_COOLDOWN_MINUTES,
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
