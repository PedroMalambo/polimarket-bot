from __future__ import annotations

from src.portfolio.paper_account import calculate_account_state, is_kill_switch_triggered


def test_calculate_account_state_with_open_and_closed_positions(monkeypatch) -> None:
    positions = [
        {
            "position_id": "pos-open-1",
            "status": "OPEN",
            "shares": 10,
            "entry_price": 0.5,
            "current_price": 0.6,
        },
        {
            "position_id": "pos-closed-1",
            "status": "CLOSED",
            "shares": 8,
            "entry_price": 0.4,
            "current_price": 0.7,
        },
    ]

    trades = [
        {
            "position_id": "pos-closed-1",
            "action": "BUY_YES_PAPER",
            "notional_usd": 3.2,
        },
        {
            "position_id": "pos-closed-1",
            "action": "SELL_YES_PAPER_TAKE_PROFIT",
            "notional_usd": 5.6,
        },
    ]

    monkeypatch.setattr("src.portfolio.paper_account.load_positions", lambda: positions)
    monkeypatch.setattr("src.portfolio.paper_account.load_trades", lambda: trades)

    result = calculate_account_state(initial_capital_usd=20)

    assert result["initial_capital_usd"] == 20
    assert result["cash_available"] == 17.4
    assert result["capital_committed"] == 5.0
    assert result["open_market_value"] == 6.0
    assert result["realized_pnl"] == 2.4
    assert result["unrealized_pnl"] == 1.0
    assert result["equity_estimate"] == 23.4
    assert result["open_positions_count"] == 1
    assert result["closed_positions_count"] == 1


def test_calculate_account_state_with_no_positions(monkeypatch) -> None:
    monkeypatch.setattr("src.portfolio.paper_account.load_positions", lambda: [])
    monkeypatch.setattr("src.portfolio.paper_account.load_trades", lambda: [])

    result = calculate_account_state(initial_capital_usd=20)

    assert result["cash_available"] == 20
    assert result["capital_committed"] == 0
    assert result["open_market_value"] == 0
    assert result["realized_pnl"] == 0
    assert result["unrealized_pnl"] == 0
    assert result["equity_estimate"] == 20
    assert result["open_positions_count"] == 0
    assert result["closed_positions_count"] == 0


def test_is_kill_switch_triggered() -> None:
    assert is_kill_switch_triggered(equity_estimate=9.99, kill_switch_usd=10) is True
    assert is_kill_switch_triggered(equity_estimate=10.0, kill_switch_usd=10) is True
    assert is_kill_switch_triggered(equity_estimate=10.01, kill_switch_usd=10) is False
