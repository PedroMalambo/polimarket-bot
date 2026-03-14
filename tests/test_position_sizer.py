from __future__ import annotations

import pytest

from src.risk.position_sizer import (
    calculate_position_plan,
    get_capital_phase,
    get_risk_fraction,
)


def test_get_risk_fraction_by_capital_tiers() -> None:
    assert get_risk_fraction(20) == 0.20
    assert get_risk_fraction(150) == 0.10
    assert get_risk_fraction(700) == 0.05


def test_get_capital_phase_by_capital_tiers() -> None:
    assert get_capital_phase(20) == "PHASE_A_ACCELERATION"
    assert get_capital_phase(150) == "PHASE_B_GROWTH"
    assert get_capital_phase(700) == "PHASE_C_CONSOLIDATION"


def test_calculate_position_plan_phase_a() -> None:
    result = calculate_position_plan(
        current_capital=20,
        entry_price=0.62,
        max_slippage_pct=0.02,
    )

    assert result["phase"] == "PHASE_A_ACCELERATION"
    assert result["risk_fraction"] == 0.20
    assert result["risk_amount_usd"] == 4.0
    assert result["entry_price"] == 0.62
    assert result["max_entry_price_with_slippage"] == 0.6324
    assert result["estimated_shares"] == 6.3251


def test_calculate_position_plan_invalid_capital() -> None:
    with pytest.raises(ValueError, match="current_capital must be > 0"):
        calculate_position_plan(current_capital=0, entry_price=0.62)


def test_calculate_position_plan_invalid_entry_price() -> None:
    with pytest.raises(ValueError, match="entry_price must be between 0 and 1"):
        calculate_position_plan(current_capital=20, entry_price=0)

    with pytest.raises(ValueError, match="entry_price must be between 0 and 1"):
        calculate_position_plan(current_capital=20, entry_price=1)
