from __future__ import annotations

from src.config.settings import get_settings
from src.live.preflight_checks import parse_allowed_live_market_ids, run_live_preflight_checks


def evaluate_live_execution_guard(simulated_entry: dict | None) -> dict:
    settings = get_settings()
    preflight = run_live_preflight_checks()

    if simulated_entry is None:
        return {
            "allowed": False,
            "reason": "NO_SIMULATED_ENTRY",
            "details": "simulated_entry is required",
        }

    if settings.TRADING_MODE != "live":
        return {
            "allowed": False,
            "reason": "TRADING_MODE_NOT_LIVE",
            "details": f"current trading mode is {settings.TRADING_MODE}",
        }

    if not settings.LIVE_TRADING_ENABLED:
        return {
            "allowed": False,
            "reason": "LIVE_TRADING_DISABLED",
            "details": "LIVE_TRADING_ENABLED is false",
        }

    if not preflight["ready_for_live"]:
        return {
            "allowed": False,
            "reason": "LIVE_PREFLIGHT_FAILED",
            "details": preflight["failed_checks"],
        }

    allowed_market_ids = parse_allowed_live_market_ids(settings.ALLOWED_LIVE_MARKET_IDS)
    market_id = str(simulated_entry.get("market_id", ""))

    if market_id not in allowed_market_ids:
        return {
            "allowed": False,
            "reason": "MARKET_NOT_ALLOWLISTED",
            "details": {
                "market_id": market_id,
                "allowed_live_market_ids": allowed_market_ids,
            },
        }

    risk_amount_usd = float(simulated_entry.get("risk_amount_usd", 0.0) or 0.0)
    if risk_amount_usd > settings.MAX_LIVE_ORDER_USD:
        return {
            "allowed": False,
            "reason": "MAX_LIVE_ORDER_USD_EXCEEDED",
            "details": {
                "risk_amount_usd": risk_amount_usd,
                "max_live_order_usd": settings.MAX_LIVE_ORDER_USD,
            },
        }

    return {
        "allowed": True,
        "reason": "LIVE_EXECUTION_ALLOWED",
        "details": {
            "market_id": market_id,
            "risk_amount_usd": risk_amount_usd,
            "max_live_order_usd": settings.MAX_LIVE_ORDER_USD,
        },
    }
