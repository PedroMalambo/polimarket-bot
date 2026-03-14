from __future__ import annotations

import time

import httpx


class PolymarketClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def _build_url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    def _get_json(self, path: str, params: dict | None = None) -> list[dict] | dict:
        url = self._build_url(path)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_delay_seconds * attempt)

        if last_error:
            raise last_error

        raise RuntimeError("Unexpected error: request failed without captured exception")

    def get_markets_raw(
        self,
        limit: int = 50,
        active: bool = True,
        closed: bool = False,
    ) -> list[dict]:
        params = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }

        payload = self._get_json("/markets", params=params)

        if isinstance(payload, list):
            return payload
        return []

    def get_markets_summary(
        self,
        limit: int = 3,
        active: bool = True,
        closed: bool = False,
    ) -> dict:
        payload = self.get_markets_raw(limit=limit, active=active, closed=closed)
        return {
            "ok": True,
            "count": len(payload),
            "sample": payload[:2],
        }
