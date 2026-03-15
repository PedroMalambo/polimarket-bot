from src.strategy.exposure_manager import filter_candidates_by_exposure
from datetime import datetime, UTC

from src.clients.polymarket_client import PolymarketClient
from src.config.settings import get_settings
from src.execution.paper_entry import simulate_paper_entry
from src.execution.paper_trader import evaluate_open_positions, is_market_in_cooldown, open_paper_position
from src.live.execution_guard import evaluate_live_execution_guard
from src.monitoring.logger import app_logger
from src.monitoring.telegram_notifier import send_telegram_message
from src.portfolio.paper_account import calculate_account_state, is_kill_switch_triggered
from src.portfolio.ledger_store import load_positions
from src.portfolio.portfolio_valuation import calculate_open_positions_valuation
from src.strategy.market_selector import filter_candidate_markets
from src.strategy.openclaw_decider import decide_market_with_openclaw
from src.strategy.mirror_feeder import get_whale_signals # <-- NUEVO IMPORT
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
    if not health["ok"]:
        app_logger.warning(f"POLYMARKET_HEALTHCHECK_ERROR={health.get('error')}")

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
            "raw_markets_count": 0,
            "candidate_markets_count": 0,
            "top_candidates": [],
            "evaluation_result": None,
            "portfolio_summary": None,
            "account_state": None,
            "kill_switch_triggered": False,
            "simulated_entry": None,
            "paper_trade_result": None,
        }

        snapshot_path = write_snapshot(snapshot_payload)
        app_logger.info(f"SNAPSHOT_SAVED={snapshot_path}")

        return {
            "health": health,
            "candidate_markets_count": 0,
            "account_state": None,
            "kill_switch_triggered": False,
            "snapshot_path": snapshot_path,
        }

    client = PolymarketClient(base_url=settings.POLYMARKET_API_BASE)
    raw_markets = client.get_markets_raw(limit=1000, active=True, closed=False)

    candidates = filter_candidate_markets(
        markets=raw_markets,
        min_prob=0.05,
        max_prob=0.95,
        min_volume=settings.MIN_MARKET_VOLUME_USD,
        max_spread=settings.MAX_SPREAD,
    )

    positions = load_positions()
    open_market_ids = {
        str(position.get("market_id"))
        for position in positions
        if str(position.get("status", "")).upper() == "OPEN" and position.get("market_id") is not None
    }

    candidates_before_open_filter_count = len(candidates)
    excluded_open_market_candidates = [
        market for market in candidates
        if str(market.get("id")) in open_market_ids
    ]
    candidates = [
        market for market in candidates
        if str(market.get("id")) not in open_market_ids
    ]
    excluded_open_market_candidates_count = len(excluded_open_market_candidates)

    candidates_before_cooldown_filter_count = len(candidates)
    excluded_cooldown_candidates: list[tuple[dict, float | None, dict | None]] = []

    filtered_candidates = []
    for market in candidates:
        market_id = str(market.get("id"))
        in_cooldown, latest_trade, elapsed_minutes = is_market_in_cooldown(
            market_id=market_id,
            cooldown_minutes=settings.MARKET_COOLDOWN_MINUTES,
        )
        if in_cooldown:
            excluded_cooldown_candidates.append((market, elapsed_minutes, latest_trade))
            continue
        filtered_candidates.append(market)

    candidates = filtered_candidates
    excluded_cooldown_candidates_count = len(excluded_cooldown_candidates)

    app_logger.info(f"RAW_MARKETS_COUNT={len(raw_markets)}")
    app_logger.info(
        f"CANDIDATE_MARKETS_PRE_OPEN_FILTER_COUNT={candidates_before_open_filter_count}"
    )
    app_logger.info(
        f"OPEN_MARKET_CANDIDATES_EXCLUDED_COUNT={excluded_open_market_candidates_count}"
    )
    for excluded_market in excluded_open_market_candidates:
        app_logger.info(
            "OPEN_MARKET_CANDIDATE_EXCLUDED="
            f"market_id={excluded_market.get('id')} | "
            f"question={excluded_market.get('question')}"
        )
    app_logger.info(
        f"CANDIDATE_MARKETS_PRE_COOLDOWN_FILTER_COUNT={candidates_before_cooldown_filter_count}"
    )
    app_logger.info(
        f"COOLDOWN_CANDIDATES_EXCLUDED_COUNT={excluded_cooldown_candidates_count}"
    )
    for excluded_market, elapsed_minutes, latest_trade in excluded_cooldown_candidates:
        app_logger.info(
            "COOLDOWN_CANDIDATE_EXCLUDED="
            f"market_id={excluded_market.get('id')} | "
            f"question={excluded_market.get('question')} | "
            f"elapsed_minutes={elapsed_minutes} | "
            f"last_action={(latest_trade or {}).get('action')}"
        )

    # --- FILTRO DE EXPOSICIÓN SEMÁNTICA (ANTI-CONCENTRACIÓN) ---
    candidates_before_exposure_filter_count = len(candidates)
    
    current_positions = load_positions()
    open_questions = [p.get("question", "") for p in current_positions if p.get("status") == "OPEN" and p.get("question")]

    candidates, excluded_exposure_details = filter_candidates_by_exposure(
        candidates=candidates,
        open_questions=open_questions,
        threshold=0.45
    )

    app_logger.info(f"EXPOSURE_FILTER_PRE_COUNT={candidates_before_exposure_filter_count}")
    app_logger.info(f"EXPOSURE_FILTER_EXCLUDED_COUNT={len(excluded_exposure_details)}")
    
    for detail in excluded_exposure_details:
        app_logger.info(
            "EXPOSURE_CANDIDATE_EXCLUDED="
            f"market_id={detail['market_id']} | "
            f"question={detail['question']} | "
            f"reason={detail['reason']}"
        )
    # -----------------------------------------------------------

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

        send_telegram_message(
            "🔴 PAPER POSITION CLOSED\n"
            f"Market: {position['market_id']}\n"
            f"Question: {position['question']}\n"
            f"Reason: {position['close_reason']}\n"
            f"Entry: {entry_price}\n"
            f"Exit: {current_price}\n"
            f"Shares: {shares}\n"
            f"Realized PnL: {realized_pnl}"
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
    live_guard_result = None

    if kill_switch_triggered:
        app_logger.warning("Kill switch triggered. Skipping new entries.")
        send_telegram_message(
            "🛑 KILL SWITCH TRIGGERED\n"
            f"Equity Estimate: {account_state['equity_estimate']}\n"
            f"Kill Switch USD: {settings.KILL_SWITCH_USD}\n"
            f"Open Positions: {account_state['open_positions_count']}\n"
            f"Closed Positions: {account_state['closed_positions_count']}"
        )
    elif account_state["open_positions_count"] >= settings.MAX_OPEN_POSITIONS:
        app_logger.warning(
            f"MAX_OPEN_POSITIONS_REACHED="
            f"open_positions_count={account_state['open_positions_count']} | "
            f"max_open_positions={settings.MAX_OPEN_POSITIONS}"
        )
        send_telegram_message(
            "🟠 MAX OPEN POSITIONS REACHED\n"
            f"Open Positions: {account_state['open_positions_count']}\n"
            f"Max Allowed: {settings.MAX_OPEN_POSITIONS}"
        )
    elif account_state["capital_committed"] >= settings.MAX_COMMITTED_CAPITAL_USD:
        app_logger.warning(
            f"MAX_COMMITTED_CAPITAL_REACHED="
            f"capital_committed={account_state['capital_committed']} | "
            f"max_committed_capital_usd={settings.MAX_COMMITTED_CAPITAL_USD}"
        )
        send_telegram_message(
            "🟠 MAX COMMITTED CAPITAL REACHED\n"
            f"Capital Committed: {account_state['capital_committed']}\n"
            f"Max Allowed USD: {settings.MAX_COMMITTED_CAPITAL_USD}"
        )
    elif candidates:
        # --- INICIO: INTEGRACIÓN DEL MONITOR DE BALLENAS ---
        try:
            whale_signals = get_whale_signals("0x02227b8f5a9636e895607edd3185ed6ee5598ff7")
            # Extraemos IDs (conditionId o asset) de los trades de la ballena
            whale_ids = {str(s.get('conditionId', s.get('asset'))) for s in whale_signals}
            
            for market in candidates:
                if str(market.get('id')) in whale_ids:
                    market['whale_signal'] = True
                    market['score'] = market.get('score', 0) + 0.50 # Bonus masivo al score
                    app_logger.info(
                        f"🐳 ALERTA BALLENA: Mercado promovido al Top. "
                        f"Question: {market['question']} | Nuevo Score: {market['score']}"
                    )
            
            # Reordenar la lista para que las opciones de la ballena suban al TOP 5
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
            
        except Exception as e:
            app_logger.error(f"Error procesando señales de la ballena: {e}")
        # --- FIN: INTEGRACIÓN DEL MONITOR DE BALLENAS ---

        openclaw_decision_result = decide_market_with_openclaw(
            candidates=candidates[:5],
            account_state=account_state,
            trading_mode=settings.TRADING_MODE,
            max_open_positions=settings.MAX_OPEN_POSITIONS,
            max_committed_capital_usd=settings.MAX_COMMITTED_CAPITAL_USD,
            max_live_order_usd=settings.MAX_LIVE_ORDER_USD,
        )
        decision_summary = openclaw_decision_result.get("decision") or {}
        app_logger.info(
            "OPENCLAW_DECISION_RESULT="
            f"ok={openclaw_decision_result.get('ok')} | "
            f"action={decision_summary.get('action')} | "
            f"market_id={decision_summary.get('market_id')} | "
            f"confidence={decision_summary.get('confidence')} | "
            f"reason={decision_summary.get('reason')} | "
            f"session_key={openclaw_decision_result.get('session_key')} | "
            f"error={openclaw_decision_result.get('error')}"
        )

        selected_market = None

        if openclaw_decision_result.get("ok"):
            decision = openclaw_decision_result.get("decision") or {}
            decision_action = str(decision.get("action", "")).upper()
            decision_market_id = str(decision.get("market_id", "")).strip()

            if decision_action == "BUY" and decision_market_id:
                selected_market = next(
                    (market for market in candidates if str(market.get("id")) == decision_market_id),
                    None,
                )

                if selected_market is not None:
                    app_logger.info(
                        "OPENCLAW_MARKET_SELECTED="
                        f"market_id={decision_market_id} | "
                        f"confidence={decision.get('confidence')} | "
                        f"reason={decision.get('reason')} | "
                        f"max_order_usd={decision.get('max_order_usd')}"
                    )
                else:
                    app_logger.warning(
                        "OPENCLAW_MARKET_ID_NOT_FOUND_IN_CANDIDATES="
                        f"market_id={decision_market_id}"
                    )
            else:
                app_logger.warning(
                    "OPENCLAW_DECISION_SKIP="
                    f"action={decision_action} | "
                    f"reason={decision.get('reason')} | "
                    f"confidence={decision.get('confidence')}"
                )
                send_telegram_message(
                    "🔵 OPENCLAW DECISION: SKIP\n"
                    f"Reason: {decision.get('reason')}\n"
                    f"Confidence: {decision.get('confidence')}"
                )
        else:
            app_logger.warning(
                "OPENCLAW_DECISION_FAILED="
                f"error={openclaw_decision_result.get('error')} | "
                f"session_key={openclaw_decision_result.get('session_key')}"
            )

        if selected_market is None and openclaw_decision_result.get("ok") is not True:
            selected_market = candidates[0]
            app_logger.warning(
                "OPENCLAW_FALLBACK_TO_TOP_CANDIDATE="
                f"market_id={selected_market['id']}"
            )

        if selected_market is None:
            app_logger.warning("No market selected after OpenClaw decision. Skipping entry.")
        else:
            simulated_entry = simulate_paper_entry(
                market=selected_market,
                current_capital=account_state["equity_estimate"],
                max_slippage_pct=settings.MAX_SLIPPAGE_PCT,
            )
            app_logger.info(f"SIMULATED_ENTRY={simulated_entry}")

            if settings.TRADING_MODE == "live":
                live_guard_result = evaluate_live_execution_guard(simulated_entry)
                app_logger.info(f"LIVE_GUARD_RESULT={live_guard_result}")

                if live_guard_result.get("allowed"):
                    app_logger.info("🔥 INICIANDO EJECUCIÓN EN VIVO (FUEGO REAL)...")
                    try:
                        import os
                        from py_clob_client.client import ClobClient
                        from py_clob_client.clob_types import OrderArgs
                        
                        # 1. Configurar cliente criptográfico real
                        host = settings.POLYMARKET_CLOB_BASE
                        key = os.getenv("PRIVATE_KEY")
                        chain_id = 137 # Red Polygon
                        
                        clob_client = ClobClient(host, key=key, chain_id=chain_id)
                        creds = clob_client.create_or_derive_api_creds()
                        clob_client.set_api_creds(creds)
                        
                        # 2. Identificar el Token ID exacto para apostar al "YES"
                        market_info = clob_client.get_market(simulated_entry['market_id'])
                        yes_token_id = market_info['tokens'][0]['token_id']
                        
                        # 3. Preparar la orden real
                        order_args = OrderArgs(
                            price=simulated_entry['entry_price'],
                            size=simulated_entry.get('risk_amount_usd', 2.0), # Dinero real a invertir
                            side="BUY",
                            token_id=yes_token_id
                        )
                        
                        # 4. 🔥 DISPARAR ORDEN A LA BLOCKCHAIN 🔥
                        resp = clob_client.create_and_post_order(order_args)
                        
                        app_logger.info(f"✅ ORDEN REAL EJECUTADA: {resp}")
                        send_telegram_message(
                            "🔥 ¡FUEGO REAL! POSICIÓN ABIERTA\n"
                            f"Mercado: {simulated_entry['market_id']}\n"
                            f"Inversión Real: ${simulated_entry.get('risk_amount_usd', 2.0)} USD\n"
                            "¡Operación confirmada en la blockchain de Polygon!"
                        )
                    except Exception as e:
                        app_logger.error(f"❌ Error al disparar orden real: {e}")
                        send_telegram_message(f"❌ ERROR DE FUEGO REAL: {e}")
                else:
                    app_logger.warning(
                        "LIVE_EXECUTION_BLOCKED="
                        f"reason={live_guard_result.get('reason')} | "
                        f"market_id={simulated_entry['market_id']} | "
                        f"details={live_guard_result.get('details')}"
                    )
                    send_telegram_message(
                        "🛑 LIVE EXECUTION BLOCKED\n"
                        f"Reason: {live_guard_result.get('reason')}\n"
                        f"Market: {simulated_entry['market_id']}"
                    )
            else:
                paper_trade_result = open_paper_position(simulated_entry)

                if paper_trade_result.get("opened"):
                    app_logger.info(
                        f"PAPER_POSITION_OPENED="
                        f"positions_count={paper_trade_result['positions_count']} | "
                        f"trades_count={paper_trade_result['trades_count']} | "
                        f"position_id={paper_trade_result['position']['position_id']} | "
                        f"market_id={paper_trade_result['position']['market_id']}"
                    )

                    opened_position = paper_trade_result["position"]
                    send_telegram_message(
                        "🟢 PAPER POSITION OPENED\n"
                        f"Market: {opened_position['market_id']}\n"
                        f"Question: {opened_position['question']}\n"
                        f"Entry: {opened_position['entry_price']}\n"
                        f"Shares: {opened_position['shares']}\n"
                        f"Stop Loss: {opened_position['stop_loss_price']}\n"
                        f"Take Profit: {opened_position['take_profit_price']}"
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

                        send_telegram_message(
                            "🟡 PAPER POSITION SKIPPED\n"
                            f"Reason: {skip_reason}\n"
                            f"Market: {simulated_entry['market_id']}\n"
                            f"Existing Position ID: {existing_position.get('position_id')}\n"
                            f"Existing Entry: {existing_position.get('entry_price')}\n"
                            f"Existing Current: {existing_position.get('current_price')}"
                        )
                    elif skip_reason == "MARKET_COOLDOWN_ACTIVE":
                        latest_trade = paper_trade_result.get("latest_trade", {})
                        skip_message += (
                            f" | cooldown_minutes={paper_trade_result.get('cooldown_minutes')} "
                            f"| elapsed_minutes={paper_trade_result.get('elapsed_minutes')} "
                            f"| latest_trade_action={latest_trade.get('action')} "
                            f"| latest_trade_timestamp_utc={latest_trade.get('timestamp_utc')}"
                        )

                        send_telegram_message(
                            "🟡 PAPER POSITION SKIPPED\n"
                            f"Reason: {skip_reason}\n"
                            f"Market: {simulated_entry['market_id']}\n"
                            f"Cooldown Minutes: {paper_trade_result.get('cooldown_minutes')}\n"
                            f"Elapsed Minutes: {paper_trade_result.get('elapsed_minutes')}\n"
                            f"Latest Trade Action: {latest_trade.get('action')}"
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
        "live_guard_result": live_guard_result,
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