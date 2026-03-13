from __future__ import annotations

from src.portfolio.ledger_store import load_positions, load_trades


def calculate_account_state(initial_capital_usd: float) -> dict:
    positions = load_positions()
    trades = load_trades()

    open_positions = [p for p in positions if p.get("status") == "OPEN"]
    closed_positions = [p for p in positions if p.get("status") == "CLOSED"]

    total_open_cost = 0.0
    for position in open_positions:
        shares = float(position.get("shares", 0.0))
        entry_price = float(position.get("entry_price", 0.0))
        total_open_cost += shares * entry_price

    realized_pnl = 0.0
    buy_notional = {}
    sell_notional = {}

    for trade in trades:
        position_id = trade.get("position_id")
        action = str(trade.get("action", ""))
        notional = float(trade.get("notional_usd", 0.0))

        if "BUY_" in action:
            buy_notional[position_id] = buy_notional.get(position_id, 0.0) + notional
        elif "SELL_" in action:
            sell_notional[position_id] = sell_notional.get(position_id, 0.0) + notional

    for position in closed_positions:
        position_id = position.get("position_id")
        buy_value = buy_notional.get(position_id, 0.0)
        sell_value = sell_notional.get(position_id, 0.0)
        realized_pnl += sell_value - buy_value

    cash_available = initial_capital_usd - total_open_cost + realized_pnl
    equity_estimate = cash_available + total_open_cost

    return {
        "initial_capital_usd": round(initial_capital_usd, 6),
        "cash_available": round(cash_available, 6),
        "capital_committed": round(total_open_cost, 6),
        "realized_pnl": round(realized_pnl, 6),
        "equity_estimate": round(equity_estimate, 6),
        "open_positions_count": len(open_positions),
        "closed_positions_count": len(closed_positions),
    }


def is_kill_switch_triggered(equity_estimate: float, kill_switch_usd: float) -> bool:
    return equity_estimate <= kill_switch_usd
