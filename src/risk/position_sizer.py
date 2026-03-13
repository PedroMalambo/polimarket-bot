from __future__ import annotations


def get_risk_fraction(current_capital: float) -> float:
    if current_capital < 100:
        return 0.20
    if current_capital < 500:
        return 0.10
    return 0.05


def get_capital_phase(current_capital: float) -> str:
    if current_capital < 100:
        return "PHASE_A_ACCELERATION"
    if current_capital < 500:
        return "PHASE_B_GROWTH"
    return "PHASE_C_CONSOLIDATION"


def calculate_position_plan(
    current_capital: float,
    entry_price: float,
    max_slippage_pct: float = 0.02,
) -> dict:
    if current_capital <= 0:
        raise ValueError("current_capital must be > 0")

    if entry_price <= 0 or entry_price >= 1:
        raise ValueError("entry_price must be between 0 and 1")

    risk_fraction = get_risk_fraction(current_capital)
    phase = get_capital_phase(current_capital)

    risk_amount_usd = round(current_capital * risk_fraction, 4)
    max_entry_price = round(entry_price * (1 + max_slippage_pct), 6)

    estimated_shares = 0.0
    if max_entry_price > 0:
        estimated_shares = round(risk_amount_usd / max_entry_price, 4)

    return {
        "phase": phase,
        "current_capital": round(current_capital, 4),
        "risk_fraction": risk_fraction,
        "risk_amount_usd": risk_amount_usd,
        "entry_price": round(entry_price, 6),
        "max_entry_price_with_slippage": max_entry_price,
        "estimated_shares": estimated_shares,
    }
