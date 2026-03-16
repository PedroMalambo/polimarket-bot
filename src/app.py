import os
from datetime import datetime, UTC

# --- IMPORTS ---
from src.clients.polymarket_client import PolymarketClient
from src.config.settings import get_settings
from src.strategy.market_selector import filter_candidate_markets
from src.strategy.openclaw_decider import decide_market_with_openclaw
from src.strategy.exposure_manager import filter_candidates_by_exposure
from src.strategy.mirror_feeder import get_whale_signals
from src.execution.paper_entry import simulate_paper_entry
from src.execution.paper_trader import evaluate_open_positions, is_market_in_cooldown, open_paper_position
from src.live.execution_guard import evaluate_live_execution_guard
from src.portfolio.live_account import get_real_polymarket_balance
from src.portfolio.paper_account import calculate_account_state, is_kill_switch_triggered
from src.portfolio.ledger_store import load_positions
from src.portfolio.portfolio_valuation import calculate_open_positions_valuation
from src.monitoring.logger import app_logger
from src.monitoring.telegram_notifier import send_telegram_message
from src.utils.healthcheck import run_polymarket_healthcheck
from src.utils.snapshot_store import write_snapshot

def run_bot_cycle() -> dict:
    settings = get_settings()

    # 1. LOG DE CONFIGURACIÓN
    app_logger.info(f"--- STARTING CYCLE: {settings.APP_NAME} ({settings.APP_ENV}) ---")
    
    # 2. HEALTHCHECK + ALERTA DE CAÍDA
    health = run_polymarket_healthcheck()
    if not health["ok"]:
        err_msg = f"⚠️ **CRITICAL: POLYMARKET API DOWN**\nError: {health.get('error')}"
        app_logger.warning(err_msg)
        send_telegram_message(err_msg) # ALERTA: Problemas de conexión
        return {
            "health": health, 
            "candidate_markets_count": 0,
            "account_state": None,
            "kill_switch_triggered": False,
            "snapshot_path": None
        }

    # 3. FILTRADO TÉCNICO INICIAL
    client = PolymarketClient(base_url=settings.POLYMARKET_API_BASE)
    raw_markets = client.get_markets_raw(limit=1000, active=True, closed=False)
    
    candidates = filter_candidate_markets(
        markets=raw_markets,
        min_prob=0.05, max_prob=0.95,
        min_volume=settings.MIN_MARKET_VOLUME_USD,
        max_spread=settings.MAX_SPREAD,
    )

    # 4. FILTROS DE EXCLUSIÓN
    positions = load_positions()
    open_market_ids = {str(p.get("market_id")) for p in positions if str(p.get("status")).upper() == "OPEN"}

    # A. Exclusión por Posición Abierta
    candidates = [m for m in candidates if str(m.get("id")) not in open_market_ids]

    # B. Exclusión por Cooldown
    final_candidates = []
    for m in candidates:
        m_id = str(m.get("id"))
        in_cooldown, last_trade, elapsed = is_market_in_cooldown(m_id, settings.MARKET_COOLDOWN_MINUTES)
        if not in_cooldown:
            final_candidates.append(m)
    candidates = final_candidates

    # C. Filtro de Exposición Semántica
    open_questions = [p.get("question", "") for p in positions if str(p.get("status")).upper() == "OPEN"]
    candidates, excluded_exp = filter_candidates_by_exposure(candidates, open_questions, threshold=0.45)

    # 5. EVALUACIÓN DE PORTFOLIO (TP/SL)
    eval_res = evaluate_open_positions(raw_markets)
    for pos in eval_res["closed_positions"]:
        pnl_text = f"Profit/Loss: ${pos.get('realized_pnl', 'N/A')}"
        send_telegram_message(f"🔴 **POSICIÓN CERRADA**\n{pos['question']}\nMotivo: {pos['close_reason']}\n{pnl_text}")

    # 6. ESTADO DE CUENTA
    account_state = calculate_account_state(settings.INITIAL_CAPITAL_USD)
    live_bal = get_real_polymarket_balance()
    if live_bal > 0:
        account_state["cash_available"] = round(live_bal, 6)
        account_state["equity_estimate"] = round(live_bal + account_state["open_market_value"], 6)

    kill_switch = is_kill_switch_triggered(account_state["equity_estimate"], settings.KILL_SWITCH_USD)
    app_logger.info(f"ACCOUNT: Equity=${account_state['equity_estimate']} | KillSwitch={kill_switch}")

    # 7. LÓGICA DE SELECCIÓN Y EJECUCIÓN
    simulated_entry, paper_res, live_res = None, None, None

    if not kill_switch and candidates and account_state["open_positions_count"] < settings.MAX_OPEN_POSITIONS:
        
        # --- ALERTA: WHALE RADAR ---
        try:
            whales = get_whale_signals("0x02227b8f5a9636e895607edd3185ed6ee5598ff7")
            whale_ids = {str(s.get('market', s.get('conditionId', s.get('asset')))) for s in whales}
            
            if whale_ids:
                whale_alert = f"🐳 **RADAR DE BALLENAS**\nSe detectaron {len(whale_ids)} señales frescas. Priorizando mercados..."
                send_telegram_message(whale_alert) # ALERTA: Actividad de ballenas detectada

            for m in candidates:
                if str(m.get('id')) in whale_ids:
                    m['score'] = m.get('score', 0) + 0.50
                    app_logger.info(f"🐳 WHALE BOOST: {m['question']}")
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        except Exception as e:
            app_logger.error(f"Whale Error: {e}")

        # --- DECISIÓN OPENCLAW ---
        decision_res = decide_market_with_openclaw(
            candidates=candidates[:5], 
            account_state=account_state, 
            trading_mode=settings.TRADING_MODE,
            max_open_positions=settings.MAX_OPEN_POSITIONS,
            max_committed_capital_usd=settings.MAX_COMMITTED_CAPITAL_USD,
            max_live_order_usd=settings.MAX_LIVE_ORDER_USD
        )
        
        if decision_res.get("ok"):
            decision = decision_res["decision"]
            action = str(decision.get("action", "")).upper()
            
            # --- ALERTA: OPENCLAW INSIGHTS (Incluso si es SKIP) ---
            if decision.get("confidence", 0) > 0.65:
                insight_msg = (
                    f"🧠 **INSIGHT DE IA ({action})**\n"
                    f"Confianza: {decision.get('confidence')}\n"
                    f"Razonamiento: {decision.get('reason')}"
                )
                send_telegram_message(insight_msg)

            if action in ["BUY_YES", "BUY_NO", "BUY"]:
                m_id = decision.get("market_id")
                selected = next((m for m in candidates if str(m['id']) == m_id), None)
                
                if selected:
                    simulated_entry = simulate_paper_entry(selected, account_state["equity_estimate"], settings.MAX_SLIPPAGE_PCT)
                    simulated_entry["side"] = "BUY_NO" if action == "BUY_NO" else "BUY_YES"

                    if settings.TRADING_MODE == "live":
                        live_res = evaluate_live_execution_guard(simulated_entry)
                        if live_res.get("allowed"):
                            try:
                                from py_clob_client.client import ClobClient
                                from py_clob_client.clob_types import OrderArgs
                                
                                clob = ClobClient(settings.POLYMARKET_CLOB_BASE, key=os.getenv("PRIVATE_KEY"), chain_id=137)
                                clob.set_api_creds(clob.create_or_derive_api_creds())
                                
                                market_info = clob.get_market(m_id)
                                token_idx = 1 if action == "BUY_NO" else 0
                                token_id = market_info['tokens'][token_idx]['token_id']
                                
                                price = simulated_entry['entry_price']
                                if action == "BUY_NO":
                                    price = round(1.0 - price, 4)

                                resp = clob.create_and_post_order(OrderArgs(
                                    price=price,
                                    size=simulated_entry.get('risk_amount_usd', 2.0),
                                    side="BUY", token_id=token_id
                                ))
                                app_logger.info(f"🔥 REAL ORDER ({action}): {resp}")
                                # ALERTA: Éxito en Fuego Real
                                send_telegram_message(f"🔥 **FUEGO REAL EJECUTADO**\n{action} en {selected['question']}\nInvertido: ${simulated_entry.get('risk_amount_usd')} USD")
                            except Exception as e:
                                err_exec = f"❌ **ERROR DE EJECUCIÓN REAL**\nMercado: {m_id}\nError: {str(e)}"
                                app_logger.error(err_exec)
                                send_telegram_message(err_exec)
                    else:
                        paper_res = open_paper_position(simulated_entry)
                        if paper_res.get("opened"):
                            send_telegram_message(f"🟢 **POSICIÓN PAPER ABIERTA**\n{action} en {selected['question']}\nPrecio: {simulated_entry['entry_price']}")

    # 8. SNAPSHOT FINAL + RESUMEN DE CICLO
    snapshot_path = write_snapshot({
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "account_state": account_state,
        "kill_switch": kill_switch,
        "execution": {"simulated": simulated_entry, "paper": paper_res, "live": live_res}
    })
    
    # --- ALERTA: RESUMEN DE CICLO ---
    summary_msg = (
        f"📋 **RESUMEN DE CICLO**\n"
        f"Equity: ${account_state['equity_estimate']}\n"
        f"Cash: ${account_state['cash_available']}\n"
        f"Posiciones: {account_state['open_positions_count']}/{settings.MAX_OPEN_POSITIONS}\n"
        f"Mercados Analizados: {len(candidates)}"
    )
    # Enviamos resumen solo si hubo actividad o cada cierto tiempo (ej. cada hora) para no saturar
    # app_logger.info(summary_msg) 
    # send_telegram_message(summary_msg) 

    app_logger.info(f"CYCLE COMPLETE. Snapshot: {snapshot_path}")

    return {
        "health": health,
        "candidate_markets_count": len(candidates),
        "account_state": account_state,
        "kill_switch_triggered": kill_switch,
        "snapshot_path": snapshot_path
    }