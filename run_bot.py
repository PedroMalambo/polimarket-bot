import time

from src.app import run_bot_cycle
from src.monitoring.logger import app_logger


def main() -> None:
    interval_seconds = 300
    max_iterations = 1000000

    app_logger.info(
        f"BOT_LOOP_START interval_seconds={interval_seconds} max_iterations={max_iterations}"
    )

    for iteration in range(1, max_iterations + 1):
        app_logger.info(f"BOT_LOOP_ITERATION_START={iteration}")

        try:
            result = run_bot_cycle()
            app_logger.info(
                f"BOT_LOOP_ITERATION_DONE={iteration} | "
                f"candidate_markets_count={result['candidate_markets_count']} | "
                f"kill_switch_triggered={result['kill_switch_triggered']} | "
                f"snapshot_path={result['snapshot_path']}"
            )
        except Exception as exc:
            app_logger.exception(f"BOT_LOOP_ITERATION_FAILED={iteration} | error={exc}")

        if iteration < max_iterations:
            app_logger.info(f"BOT_LOOP_SLEEP={interval_seconds}s")
            time.sleep(interval_seconds)

    app_logger.info("BOT_LOOP_END")


if __name__ == "__main__":
    main()
