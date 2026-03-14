from __future__ import annotations

from src.execution.paper_trader import evaluate_open_positions, open_paper_position


def test_open_paper_position_success(monkeypatch) -> None:
    simulated_entry = {
        "market_id": "m1",
        "question": "Test market?",
        "entry_price": 0.62,
        "max_entry_price_with_slippage": 0.6324,
        "estimated_shares": 6.3,
        "risk_amount_usd": 4.0,
        "phase": "PHASE_A_ACCELERATION",
        "stop_loss_price": 0.52,
        "take_profit_price": 0.95,
        "score": 0.4,
    }

    positions_store = []
    trades_store = []

    monkeypatch.setattr("src.execution.paper_trader.ensure_ledger_files", lambda: None)
    monkeypatch.setattr("src.execution.paper_trader.find_open_position_by_market_id", lambda market_id: None)
    monkeypatch.setattr(
        "src.execution.paper_trader.get_settings",
        lambda: type("S", (), {"MARKET_COOLDOWN_MINUTES": 60})(),
    )
    monkeypatch.setattr(
        "src.execution.paper_trader.is_market_in_cooldown",
        lambda market_id, cooldown_minutes: (False, None, None),
    )
    monkeypatch.setattr("src.execution.paper_trader.load_positions", lambda: positions_store)
    monkeypatch.setattr("src.execution.paper_trader.load_trades", lambda: trades_store)
    monkeypatch.setattr("src.execution.paper_trader.save_positions", lambda positions: None)
    monkeypatch.setattr("src.execution.paper_trader.save_trades", lambda trades: None)
    monkeypatch.setattr("src.execution.paper_trader.utc_now_iso", lambda: "2026-03-14T00:00:00+00:00")

    result = open_paper_position(simulated_entry)

    assert result["opened"] is True
    assert result["positions_count"] == 1
    assert result["trades_count"] == 1
    assert positions_store[0]["market_id"] == "m1"
    assert positions_store[0]["status"] == "OPEN"
    assert trades_store[0]["action"] == "BUY_YES_PAPER"


def test_open_paper_position_existing_open_position(monkeypatch) -> None:
    existing_position = {
        "position_id": "existing-pos-1",
        "market_id": "m1",
        "status": "OPEN",
    }

    monkeypatch.setattr("src.execution.paper_trader.ensure_ledger_files", lambda: None)
    monkeypatch.setattr(
        "src.execution.paper_trader.find_open_position_by_market_id",
        lambda market_id: existing_position,
    )

    result = open_paper_position({"market_id": "m1"})

    assert result["opened"] is False
    assert result["reason"] == "OPEN_POSITION_ALREADY_EXISTS"
    assert result["existing_position"]["position_id"] == "existing-pos-1"


def test_open_paper_position_market_cooldown_active(monkeypatch) -> None:
    latest_trade = {
        "trade_id": "t1",
        "market_id": "m2",
        "action": "SELL_YES_PAPER_TAKE_PROFIT",
        "timestamp_utc": "2026-03-14T00:10:00+00:00",
    }

    monkeypatch.setattr("src.execution.paper_trader.ensure_ledger_files", lambda: None)
    monkeypatch.setattr("src.execution.paper_trader.find_open_position_by_market_id", lambda market_id: None)
    monkeypatch.setattr(
        "src.execution.paper_trader.get_settings",
        lambda: type("S", (), {"MARKET_COOLDOWN_MINUTES": 60})(),
    )
    monkeypatch.setattr(
        "src.execution.paper_trader.is_market_in_cooldown",
        lambda market_id, cooldown_minutes: (True, latest_trade, 12.5),
    )

    result = open_paper_position({"market_id": "m2"})

    assert result["opened"] is False
    assert result["reason"] == "MARKET_COOLDOWN_ACTIVE"
    assert result["latest_trade"]["trade_id"] == "t1"
    assert result["elapsed_minutes"] == 12.5
    assert result["cooldown_minutes"] == 60


def test_evaluate_open_positions_closes_take_profit(monkeypatch) -> None:
    positions_store = [
        {
            "position_id": "pos-1",
            "market_id": "m1",
            "question": "Test market?",
            "status": "OPEN",
            "shares": 10,
            "entry_price": 0.62,
            "current_price": 0.62,
            "phase": "PHASE_A_ACCELERATION",
            "stop_loss_price": 0.52,
            "take_profit_price": 0.95,
            "closed_at_utc": None,
            "close_reason": None,
        }
    ]
    trades_store = []

    latest_candidates = [{"id": "m1", "yes_price": 0.96}]

    monkeypatch.setattr("src.execution.paper_trader.ensure_ledger_files", lambda: None)
    monkeypatch.setattr("src.execution.paper_trader.load_positions", lambda: positions_store)
    monkeypatch.setattr("src.execution.paper_trader.load_trades", lambda: trades_store)
    monkeypatch.setattr("src.execution.paper_trader.save_positions", lambda positions: None)
    monkeypatch.setattr("src.execution.paper_trader.save_trades", lambda trades: None)
    monkeypatch.setattr("src.execution.paper_trader.utc_now_iso", lambda: "2026-03-14T00:20:00+00:00")

    result = evaluate_open_positions(latest_candidates)

    assert result["closed_positions_count"] == 1
    assert positions_store[0]["status"] == "CLOSED"
    assert positions_store[0]["close_reason"] == "TAKE_PROFIT"
    assert positions_store[0]["current_price"] == 0.96
    assert trades_store[0]["action"] == "SELL_YES_PAPER_TAKE_PROFIT"
    assert trades_store[0]["notional_usd"] == 9.6


def test_evaluate_open_positions_closes_stop_loss(monkeypatch) -> None:
    positions_store = [
        {
            "position_id": "pos-2",
            "market_id": "m2",
            "question": "Another market?",
            "status": "OPEN",
            "shares": 5,
            "entry_price": 0.7,
            "current_price": 0.7,
            "phase": "PHASE_A_ACCELERATION",
            "stop_loss_price": 0.5,
            "take_profit_price": 0.95,
            "closed_at_utc": None,
            "close_reason": None,
        }
    ]
    trades_store = []

    latest_candidates = [{"id": "m2", "yes_price": 0.49}]

    monkeypatch.setattr("src.execution.paper_trader.ensure_ledger_files", lambda: None)
    monkeypatch.setattr("src.execution.paper_trader.load_positions", lambda: positions_store)
    monkeypatch.setattr("src.execution.paper_trader.load_trades", lambda: trades_store)
    monkeypatch.setattr("src.execution.paper_trader.save_positions", lambda positions: None)
    monkeypatch.setattr("src.execution.paper_trader.save_trades", lambda trades: None)
    monkeypatch.setattr("src.execution.paper_trader.utc_now_iso", lambda: "2026-03-14T00:30:00+00:00")

    result = evaluate_open_positions(latest_candidates)

    assert result["closed_positions_count"] == 1
    assert positions_store[0]["status"] == "CLOSED"
    assert positions_store[0]["close_reason"] == "STOP_LOSS"
    assert positions_store[0]["current_price"] == 0.49
    assert trades_store[0]["action"] == "SELL_YES_PAPER_STOP_LOSS"
    assert trades_store[0]["notional_usd"] == 2.45
