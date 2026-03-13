from __future__ import annotations

from src.risk.position_sizer import calculate_position_plan


def simulate_paper_entry(market: dict, current_capital: float, max_slippage_pct: float = 0.02) -> dict:
    yes_price = market.get("yes_price")
    if yes_price is None:
        raise ValueError("market yes_price is missing")

    position = calculate_position_plan(
        current_capital=current_capital,
        entry_price=yes_price,
        max_slippage_pct=max_slippage_pct,
    )

    stop_loss_price = round(yes_price * (1 - 0.15), 6)
    take_profit_price = 0.95

    return {
        "market_id": market.get("id"),
        "question": market.get("question"),
        "yes_price": yes_price,
        "score": market.get("score"),
        "volume": market.get("volume"),
        "liquidity": market.get("liquidity"),
        "spread": market.get("spread"),
        "phase": position["phase"],
        "risk_fraction": position["risk_fraction"],
        "risk_amount_usd": position["risk_amount_usd"],
        "estimated_shares": position["estimated_shares"],
        "entry_price": position["entry_price"],
        "max_entry_price_with_slippage": position["max_entry_price_with_slippage"],
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
    }
