import time
import traceback
from src.app import run_bot_cycle
from src.monitoring.daily_summary import (
    build_daily_summary_message,
    mark_daily_summary_sent,
    should_send_daily_summary,
)
from src.monitoring.logger import app_logger
from src.monitoring.telegram_notifier import send_telegram_message
from src.reporting.dashboard_generator import generate_dashboard

def main() -> None:
    interval_seconds = 300
    max_iterations = 1000000

    # --- ALERTA DE INICIO ---
    startup_msg = (
        "🚀 **POLMARKET BOT ONLINE**\n"
        "------------------------------\n"
        f"El sistema ha arrancado con éxito.\n"
        f"Intervalo: {interval_seconds}s\n"
        "Vigilando mercados... 📈"
    )
    send_telegram_message(startup_msg)
    app_logger.info(f"BOT_LOOP_START interval_seconds={interval_seconds}")

    for iteration in range(1, max_iterations + 1):
        app_logger.info(f"BOT_LOOP_ITERATION_START={iteration}")

        try:
            # Ejecutamos el ciclo principal
            result = run_bot_cycle()
            
            app_logger.info(
                f"BOT_LOOP_ITERATION_DONE={iteration} | "
                f"markets={result.get('candidate_markets_count')} | "
                f"kill_switch={result.get('kill_switch_triggered')}"
            )

            # --- LÓGICA DE RESUMEN DIARIO ---
            account_state = result.get("account_state")
            if account_state and should_send_daily_summary():
                summary_message = build_daily_summary_message(
                    account_state=account_state,
                    kill_switch_triggered=result.get("kill_switch_triggered", False),
                )
                if send_telegram_message(summary_message):
                    mark_daily_summary_sent()
                    app_logger.info("DAILY_SUMMARY_SENT=True")

            # Generamos dashboard visual
            dashboard_path = generate_dashboard()
            app_logger.info(f"DASHBOARD_GENERATED={dashboard_path}")

        except Exception as exc:
            # --- ALERTA DE ERROR CRÍTICO ---
            # Si el bot falla, te envía el error exacto a Telegram
            error_trace = traceback.format_exc()
            error_msg = (
                f"⚠️ **BOT LOOP FAILED (Iteración {iteration})**\n"
                f"Error: `{str(exc)}`"
            )
            send_telegram_message(error_msg)
            app_logger.exception(f"BOT_LOOP_ITERATION_FAILED={iteration} | error={exc}")

        # Tiempo de espera entre ciclos
        if iteration < max_iterations:
            app_logger.info(f"BOT_LOOP_SLEEP={interval_seconds}s")
            time.sleep(interval_seconds)

    send_telegram_message("🛑 **BOT_LOOP_END**: El bot ha finalizado todas sus iteraciones.")
    app_logger.info("BOT_LOOP_END")


if __name__ == "__main__":
    main()
