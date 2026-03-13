from __future__ import annotations

from src.portfolio.ledger_store import load_positions


def build_market_price_map(candidates: list[dict]) -> dict[str, float]:
    price_map: dict[str, float] = {}
    for market in candidates:
        market_id = str(market.get("id"))
        yes_price = market.get("yes_price")
        if market_id and yes_price is not None:
            price_map[market_id] = float(yes_price)
    return price_map


def calculate_open_positions_valuation(candidates: list[dict]) -> dict:
    positions = load_positions()
    price_map = build_market_price_map(candidates)

    open_positions = [p for p in positions if p.get("status") == "OPEN"]
    valued_positions: list[dict] = []

    total_cost = 0.0
    total_market_value = 0.0
    total_unrealized_pnl = 0.0

    for position in open_positions:
        market_id = str(position.get("market_id"))
        current_price = price_map.get(market_id, position.get("current_price", position.get("entry_price", 0.0)))

        shares = float(position.get("shares", 0.0))
        entry_price = float(position.get("entry_price", 0.0))

        cost_basis = round(shares * entry_price, 6)
        market_value = round(shares * current_price, 6)
        unrealized_pnl = round(market_value - cost_basis, 6)

        unrealized_pnl_pct = 0.0
        if cost_basis > 0:
            unrealized_pnl_pct = round(unrealized_pnl / cost_basis, 6)

        valued = {
            "position_id": position.get("position_id"),
            "market_id": market_id,
            "question": position.get("question"),
            "shares": shares,
            "entry_price": entry_price,
            "current_price": current_price,
            "cost_basis": cost_basis,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "stop_loss_price": position.get("stop_loss_price"),
            "take_profit_price": position.get("take_profit_price"),
            "status": position.get("status"),
        }
        valued_positions.append(valued)

        total_cost += cost_basis
        total_market_value += market_value
        total_unrealized_pnl += unrealized_pnl

    portfolio_unrealized_pnl_pct = 0.0
    if total_cost > 0:
        portfolio_unrealized_pnl_pct = round(total_unrealized_pnl / total_cost, 6)

    return {
        "open_positions_count": len(open_positions),
        "valued_positions": valued_positions,
        "total_cost": round(total_cost, 6),
        "total_market_value": round(total_market_value, 6),
        "total_unrealized_pnl": round(total_unrealized_pnl, 6),
        "total_unrealized_pnl_pct": portfolio_unrealized_pnl_pct,
    }
