from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.live.preflight_checks import run_live_preflight_checks


def main() -> None:
    result = run_live_preflight_checks()

    print(f"READY_FOR_LIVE={result['ready_for_live']}")
    print(f"TRADING_MODE={result['trading_mode']}")
    print("")

    print("CHECKS:")
    for check in result["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(
            f"- {status} | {check['name']} | "
            f"value={check['value']} | reason={check['reason']}"
        )

    print("")
    print("FAILED_CHECKS:")
    if not result["failed_checks"]:
        print("- none")
    else:
        for check in result["failed_checks"]:
            print(
                f"- {check['name']} | "
                f"value={check['value']} | reason={check['reason']}"
            )


if __name__ == "__main__":
    main()
