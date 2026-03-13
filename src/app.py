from datetime import datetime, UTC

from src.clients.polymarket_client import PolymarketClient
from src.config.settings import get_settings
from src.execution.paper_entry import simulate_paper_entry
from src.execution.paper_trader import evaluate_open_positions, open_paper_position
from src.monitoring.logger import app_logger
from src.portfolio.paper_account import calculate_account_state, is_kill_switch_triggered
from src.portfolio.portfolio_valuation import calculate_open_positions_valuation
from src.strategy.market_selector import filter_candidate_markets
from src.utils.healthcheck import run_polymarket_healthcheck
from src.utils.snapshot_store import write_snapshot


def run_bot_cycle() -> dict:
    settings = get_settings()

    app_logger.info("Starting application")
    app_logger.info(f"APP_NAME={settings.APP_NAME}")
    app_logger.info(f"APP_ENV={settings.APP_ENV}")
    app_logger.info(f"POLYMARKET_API_BASE={settings.POLYMARKET_API_BASE}")
    app_logger.info(f"POLYMARKET_CLOB_BASE={settings.POLYMARKET_CLOB_BASE}")
    app_logger.info(f"INITIAL_CAPITAL_USD={settings.INITIAL_CAPITAL_USD}")
    app_logger.info(f"KILL_SWITCH_USD={settings.KILL_SWITCH_USD}")
    app_logger.info(f"MIN_MARKET_VOLUME_USD={settings.MIN_MARKET_VOLUME_USD}")
    app_logger.info(f"MAX_SPREAD={settings.MAX_SPREAD}")
    app_logger.info(f"MAX_SLIPPAGE_PCT={settings.MAX_SLIPPAGE_PCT}")
    app_logger.info(f"MAX_OPEN_POSITIONS={settings.MAX_OPEN_POSITIONS}")
    app_logger.info(f"MARKET_COOLDOWN_MINUTES={settings.MARKET_COOLDOWN_MINUTES}")
    app_logger.info(f"MAX_COMMITTED_CAPITAL_USD={settings.MAX_COMMITTED_CAPITAL_USD}")

    health = run_polymarket_healthcheck()
    app_logger.info(f"POLYMARKET_HEALTHCHECK_OK={health['ok']}")
    app_logger.info(f"POLYMARKET_HEALTHCHECK_COUNT={health['count']}")

    client = PolymarketClient(base_url=settings.POLYMARKET_API_BASE)
    raw_markets = client.get_markets_raw(limit=100, active=True, closed=False)

    candidates = filter_candidate_markets(
        markets=raw_markets,
        min_prob=0.60,
        max_prob=0.80,
        min_volume=settings.MIN_MARKET_VOLUME_USD,
        max_spread=settings.MAX_SPREAD,
    )

    app_logger.info(f"RAW_MARKETS_COUNT={len(raw_markets)}")
    app_logger.info(f"CANDIDATE_MARKETS_COUNT={len(candidates)}")

    for idx, market in enumerate(candidates[:10], start=1):
        app_logger.info(
            f"RANKED_CANDIDATE_{idx}="
            f"score={market['score']} | "
            f"id={market['id']} | "
            f"yes_price={market['yes_price']} | "
            f"volume={market['volume']} | "
            f"liquidity={market['liquidity']} | "
            f"best_bid={market['best_bid']} | "
            f"best_ask={market['best_ask']} | "
            f"spread={market['spread']} | "
            f"question={market['question']}"
        )

    evaluation_result = evaluate_open_positions(raw_markets)
    app_logger.info(
        f"POSITION_EVALUATION="
        f"closed_positions_count={evaluation_result['closed_positions_count']} | "
        f"positions_count={evaluation_result['positions_count']} | "
        f"trades_count={evaluation_result['trades_count']}"
    )

    for idx, position in enumerate(evaluation_result["closed_positions"], start=1):
        entry_price = float(position.get("entry_price", 0.0))
        current_price = float(position.get("current_price", entry_price))
        shares = float(position.get("shares", 0.0))
        realized_pnl = round((current_price - entry_price) * shares, 6)

        app_logger.info(
            f"CLOSED_POSITION_{idx}="
            f"market_id={position['market_id']} | "
            f"question={position['question']} | "
            f"close_reason={position['close_reason']} | "
            f"entry_price={entry_price} | "
            f"exit_price={current_price} | "
            f"shares={shares} | "
            f"realized_pnl={realized_pnl} | "
            f"closed_at_utc={position['closed_at_utc']}"
        )

    portfolio_summary = calculate_open_positions_valuation(raw_markets)
    app_logger.info(
        f"PORTFOLIO_SUMMARY="
        f"open_positions_count={portfolio_summary['open_positions_count']} | "
        f"total_cost={portfolio_summary['total_cost']} | "
        f"total_market_value={portfolio_summary['total_market_value']} | "
        f"total_unrealized_pnl={portfolio_summary['total_unrealized_pnl']} | "
        f"total_unrealized_pnl_pct={portfolio_summary['total_unrealized_pnl_pct']}"
    )

    for idx, position in enumerate(portfolio_summary["valued_positions"], start=1):
        app_logger.info(
            f"OPEN_POSITION_{idx}="
            f"market_id={position['market_id']} | "
            f"entry_price={position['entry_price']} | "
            f"current_price={position['current_price']} | "
            f"shares={position['shares']} | "
            f"cost_basis={position['cost_basis']} | "
            f"market_value={position['market_value']} | "
            f"unrealized_pnl={position['unrealized_pnl']} | "
            f"unrealized_pnl_pct={position['unrealized_pnl_pct']} | "
            f"question={position['question']}"
        )

    account_state = calculate_account_state(settings.INITIAL_CAPITAL_USD)
    kill_switch_triggered = is_kill_switch_triggered(
        equity_estimate=account_state["equity_estimate"],
        kill_switch_usd=settings.KILL_SWITCH_USD,
    )

    app_logger.info(
        f"ACCOUNT_STATE="
        f"cash_available={account_state['cash_available']} | "
        f"capital_committed={account_state['capital_committed']} | "
        f"open_market_value={account_state['open_market_value']} | "
        f"realized_pnl={account_state['realized_pnl']} | "
        f"unrealized_pnl={account_state['unrealized_pnl']} | "
        f"equity_estimate={account_state['equity_estimate']} | "
        f"open_positions_count={account_state['open_positions_count']} | "
        f"closed_positions_count={account_state['closed_positions_count']}"
    )
    app_logger.info(f"KILL_SWITCH_TRIGGERED={kill_switch_triggered}")

    simulated_entry = None
    paper_trade_result = None

    if kill_switch_triggered:
        app_logger.warning("Kill switch triggered. Skipping new entries.")
    elif account_state["open_positions_count"] >= settings.MAX_OPEN_POSITIONS:
        app_logger.warning(
            f"MAX_OPEN_POSITIONS_REACHED="
            f"open_positions_count={account_state['open_positions_count']} | "
            f"max_open_positions={settings.MAX_OPEN_POSITIONS}"
        )
    elif account_state["capital_committed"] >= settings.MAX_COMMITTED_CAPITAL_USD:
        app_logger.warning(
            f"MAX_COMMITTED_CAPITAL_REACHED="
            f"capital_committed={account_state['capital_committed']} | "
            f"max_committed_capital_usd={settings.MAX_COMMITTED_CAPITAL_USD}"
        )
    elif candidates:
        best_market = candidates[0]
        simulated_entry = simulate_paper_entry(
            market=best_market,
            current_capital=account_state["equity_estimate"],
            max_slippage_pct=settings.MAX_SLIPPAGE_PCT,
        )
        app_logger.info(f"SIMULATED_ENTRY={simulated_entry}")

        paper_trade_result = open_paper_position(simulated_entry)

        if paper_trade_result.get("opened"):
            app_logger.info(
                f"PAPER_POSITION_OPENED="
                f"positions_count={paper_trade_result['positions_count']} | "
                f"trades_count={paper_trade_result['trades_count']} | "
                f"position_id={paper_trade_result['position']['position_id']} | "
                f"market_id={paper_trade_result['position']['market_id']}"
            )
        else:
            skip_reason = paper_trade_result.get("reason", "UNKNOWN")
            skip_message = (
                f"PAPER_POSITION_SKIPPED="
                f"reason={skip_reason} | "
                f"market_id={simulated_entry['market_id']}"
            )

            if skip_reason == "OPEN_POSITION_ALREADY_EXISTS":
                existing_position = paper_trade_result.get("existing_position", {})
                skip_message += (
                    f" | existing_position_id={existing_position.get('position_id')} "
                    f"| existing_entry_price={existing_position.get('entry_price')} "
                    f"| existing_current_price={existing_position.get('current_price')} "
                    f"| existing_opened_at_utc={existing_position.get('opened_at_utc')}"
                )
            elif skip_reason == "MARKET_COOLDOWN_ACTIVE":
                latest_trade = paper_trade_result.get("latest_trade", {})
                skip_message += (
                    f" | cooldown_minutes={paper_trade_result.get('cooldown_minutes')} "
                    f"| elapsed_minutes={paper_trade_result.get('elapsed_minutes')} "
                    f"| latest_trade_action={latest_trade.get('action')} "
                    f"| latest_trade_timestamp_utc={latest_trade.get('timestamp_utc')}"
                )

            app_logger.warning(skip_message)
    else:
        app_logger.warning("No candidate markets found. Skipping paper entry simulation.")

    snapshot_payload = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "app_env": settings.APP_ENV,
        "initial_capital_usd": settings.INITIAL_CAPITAL_USD,
        "kill_switch_usd": settings.KILL_SWITCH_USD,
        "filters": {
            "min_market_volume_usd": settings.MIN_MARKET_VOLUME_USD,
            "max_spread": settings.MAX_SPREAD,
            "max_slippage_pct": settings.MAX_SLIPPAGE_PCT,
            "probability_range": [0.60, 0.80],
        },
        "healthcheck": health,
        "raw_markets_count": len(raw_markets),
        "candidate_markets_count": len(candidates),
        "top_candidates": candidates[:10],
        "evaluation_result": evaluation_result,
        "portfolio_summary": portfolio_summary,
        "account_state": account_state,
        "kill_switch_triggered": kill_switch_triggered,
        "simulated_entry": simulated_entry,
        "paper_trade_result": paper_trade_result,
    }

    snapshot_path = write_snapshot(snapshot_payload)
    app_logger.info(f"SNAPSHOT_SAVED={snapshot_path}")

    return {
        "health": health,
        "candidate_markets_count": len(candidates),
        "account_state": account_state,
        "kill_switch_triggered": kill_switch_triggered,
        "snapshot_path": snapshot_path,
    }
