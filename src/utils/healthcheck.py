from __future__ import annotations

from src.clients.polymarket_client import PolymarketClient
from src.config.settings import get_settings


def run_polymarket_healthcheck() -> dict:
    settings = get_settings()
    client = PolymarketClient(base_url=settings.POLYMARKET_API_BASE)

    try:
        return client.get_markets_summary(limit=3, active=True, closed=False)
    except Exception as exc:
        return {
            "ok": False,
            "count": 0,
            "sample": [],
            "error": str(exc),
        }
