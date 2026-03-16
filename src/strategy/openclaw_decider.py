from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from src.clients.openclaw_client import get_openclaw_client


def _extract_text_from_history_payload(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    assistant_texts: list[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", "")).lower()
        if role != "assistant":
            continue

        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        assistant_texts.append(text.strip())
        else:
            text = message.get("text")
            if isinstance(text, str) and text.strip():
                assistant_texts.append(text.strip())

    return "\n".join(assistant_texts).strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def build_openclaw_decision_prompt(
    candidates: list[dict[str, Any]],
    account_state: dict[str, Any],
    trading_mode: str,
    max_open_positions: int,
    max_committed_capital_usd: float,
    max_live_order_usd: float,
) -> str:
    payload = {
        "task": "Act as an aggressive Quantitative Analyst for a Polymarket hedge fund. Your goal is to find mispriced markets with Positive Expected Value (+EV).",
        "instructions": [
            "Return valid JSON only. Do not use markdown. Do not add explanations outside JSON.",
            "Compare the market 'yes_price' (implied probability) against real-world logic, news, and statistical probability.",
            "If the crowd is overestimating an event (price is too high), bet AGAINST them: return action=BUY_NO.",
            "If the crowd is underestimating an event (price is too low), bet with value: return action=BUY_YES.",
            "If no clear statistical edge is found or the market is efficient, return action=SKIP.",
            "Be aggressive when you find a real edge (+EV), but justify it in the 'reason' field.",
            "Only choose a market_id from the provided candidates."
        ],
        "output_schema": {
            "action": "BUY_YES, BUY_NO, or SKIP",
            "market_id": "string",
            "confidence": "float between 0 and 1",
            "reason": "detailed explanation of the mispricing and why this trade has +EV",
            "max_order_usd": "float >= 0"
        },
        "bot_context": {
            "trading_mode": trading_mode,
            "max_open_positions": max_open_positions,
            "max_committed_capital_usd": max_committed_capital_usd,
            "max_live_order_usd": max_live_order_usd,
            "account_state": account_state,
        },
        "candidates": candidates[:10],
        "examples": [
            {
                "scenario": "Market price for YES is 0.10 (10%), but you estimate true probability is 25%",
                "output": {
                    "action": "BUY_YES",
                    "market_id": "999",
                    "confidence": 0.85,
                    "reason": "Market severely underestimates YES. Buying at 0.10 with 25% true odds provides massive +EV.",
                    "max_order_usd": 3.0
                }
            },
            {
                "scenario": "Market price for YES is 0.90 (90%), but it's a volatile event with 60% real odds",
                "output": {
                    "action": "BUY_NO",
                    "market_id": "888",
                    "confidence": 0.92,
                    "reason": "YES is overvalued at 0.90. Betting NO at 0.10 is a high-value play against an irrational crowd.",
                    "max_order_usd": 3.0
                }
            }
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _wait_for_assistant_text(
    client,
    session_key: str,
    max_attempts: int = 12,
    sleep_seconds: float = 1.5,
) -> tuple[str, dict[str, Any]]:
    last_history: dict[str, Any] = {}

    for _ in range(max_attempts):
        history_payload = await client.chat_history(
            session_key=session_key,
            limit=20,
        )
        last_history = history_payload

        assistant_text = _extract_text_from_history_payload(history_payload)
        if assistant_text.strip():
            return assistant_text, history_payload

        await asyncio.sleep(sleep_seconds)

    return "", last_history


async def _decide_with_openclaw_async(
    candidates: list[dict[str, Any]],
    account_state: dict[str, Any],
    trading_mode: str,
    max_open_positions: int,
    max_committed_capital_usd: float,
    max_live_order_usd: float,
) -> dict[str, Any]:
    if not candidates:
        return {
            "ok": False,
            "send_result": None,
            "assistant_text": "",
            "decision": None,
            "error": "NO_CANDIDATES",
        }

    prompt = build_openclaw_decision_prompt(
        candidates=candidates,
        account_state=account_state,
        trading_mode=trading_mode,
        max_open_positions=max_open_positions,
        max_committed_capital_usd=max_committed_capital_usd,
        max_live_order_usd=max_live_order_usd,
    )

    session_key = f"agent:main:decision-{uuid.uuid4()}"

    async with get_openclaw_client() as client:
        send_result = await client.chat_send(
            message=prompt,
            session_key=session_key,
            deliver=False,
        )

        assistant_text, history_payload = await _wait_for_assistant_text(
            client=client,
            session_key=session_key,
            max_attempts=12,
            sleep_seconds=1.5,
        )

    decision = _extract_json_object(assistant_text)

    return {
        "ok": decision is not None,
        "send_result": send_result,
        "assistant_text": assistant_text,
        "decision": decision,
        "session_key": session_key,
        "history_payload": history_payload,
    }


def decide_market_with_openclaw(
    candidates: list[dict[str, Any]],
    account_state: dict[str, Any],
    trading_mode: str,
    max_open_positions: int,
    max_committed_capital_usd: float,
    max_live_order_usd: float,
) -> dict[str, Any]:
    try:
        return asyncio.run(
            _decide_with_openclaw_async(
                candidates=candidates,
                account_state=account_state,
                trading_mode=trading_mode,
                max_open_positions=max_open_positions,
                max_committed_capital_usd=max_committed_capital_usd,
                max_live_order_usd=max_live_order_usd,
            )
        )
    except Exception as exc:
        return {
            "ok": False,
            "send_result": None,
            "assistant_text": "",
            "decision": None,
            "error": str(exc),
        }