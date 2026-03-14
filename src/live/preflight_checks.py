from __future__ import annotations

from src.config.settings import get_settings
from src.utils.healthcheck import run_polymarket_healthcheck


def parse_allowed_live_market_ids(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def run_live_preflight_checks() -> dict:
    settings = get_settings()
    health = run_polymarket_healthcheck()
    allowed_market_ids = parse_allowed_live_market_ids(settings.ALLOWED_LIVE_MARKET_IDS)
    is_live_mode = settings.TRADING_MODE == "live"

    checks = [
        {
            "name": "trading_mode_valid",
            "ok": settings.TRADING_MODE in {"paper", "live"},
            "value": settings.TRADING_MODE,
            "reason": "TRADING_MODE must be 'paper' or 'live'",
        },
        {
            "name": "live_trading_enabled_flag",
            "ok": (not is_live_mode) or (bool(settings.LIVE_TRADING_ENABLED) is True),
            "value": settings.LIVE_TRADING_ENABLED,
            "reason": "LIVE_TRADING_ENABLED must be true when TRADING_MODE=live",
        },
        {
            "name": "private_key_present",
            "ok": (not is_live_mode) or bool(settings.PRIVATE_KEY),
            "value": bool(settings.PRIVATE_KEY),
            "reason": "PRIVATE_KEY is required when TRADING_MODE=live",
        },
        {
            "name": "polygon_rpc_present",
            "ok": (not is_live_mode) or bool(settings.POLYGON_RPC_URL),
            "value": bool(settings.POLYGON_RPC_URL),
            "reason": "POLYGON_RPC_URL is required when TRADING_MODE=live",
        },
        {
            "name": "max_live_order_usd_valid",
            "ok": settings.MAX_LIVE_ORDER_USD > 0,
            "value": settings.MAX_LIVE_ORDER_USD,
            "reason": "MAX_LIVE_ORDER_USD must be > 0",
        },
        {
            "name": "polymarket_healthcheck_ok",
            "ok": bool(health.get("ok")),
            "value": health.get("count"),
            "reason": health.get("error") or "Polymarket healthcheck failed",
        },
        {
            "name": "allowed_live_market_ids_present",
            "ok": (not is_live_mode) or (len(allowed_market_ids) > 0),
            "value": allowed_market_ids,
            "reason": "ALLOWED_LIVE_MARKET_IDS must contain at least one market when TRADING_MODE=live",
        },
    ]

    failed_checks = [check for check in checks if not check["ok"]]
    ready_for_live = is_live_mode and len(failed_checks) == 0

    return {
        "ready_for_live": ready_for_live,
        "trading_mode": settings.TRADING_MODE,
        "checks": checks,
        "failed_checks": failed_checks,
    }
