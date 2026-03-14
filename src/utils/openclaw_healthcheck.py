from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from src.clients.openclaw_client import get_openclaw_client


async def _run_openclaw_healthcheck_async() -> dict[str, Any]:
    started = perf_counter()

    try:
        async with get_openclaw_client() as client:
            payload = await client.health()

        duration_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "ok": bool(payload.get("ok", False)),
            "duration_ms": duration_ms,
            "payload": payload,
            "error": None,
        }
    except Exception as exc:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "payload": None,
            "error": str(exc),
        }


def run_openclaw_healthcheck() -> dict[str, Any]:
    return asyncio.run(_run_openclaw_healthcheck_async())
