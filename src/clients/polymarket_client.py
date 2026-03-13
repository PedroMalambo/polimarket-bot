from __future__ import annotations

import httpx


class PolymarketClient:
    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _build_url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    def get_markets_raw(self, limit: int = 50, active: bool = True, closed: bool = False) -> list[dict]:
        url = self._build_url("/markets")
        params = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if isinstance(payload, list):
            return payload
        return []

    def get_markets_summary(self, limit: int = 3, active: bool = True, closed: bool = False) -> dict:
        payload = self.get_markets_raw(limit=limit, active=active, closed=closed)
        return {
            "ok": True,
            "count": len(payload),
            "sample": payload[:2],
        }
