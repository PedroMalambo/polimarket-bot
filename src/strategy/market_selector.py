from __future__ import annotations

import json
from typing import Any


def _safe_json_loads(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_market(raw: dict) -> dict:
    outcomes = _safe_json_loads(raw.get("outcomes"))
    outcome_prices = _safe_json_loads(raw.get("outcomePrices"))

    yes_price = None
    no_price = None

    if len(outcomes) >= 2 and len(outcome_prices) >= 2:
        for outcome, price in zip(outcomes, outcome_prices):
            outcome_name = str(outcome).strip().lower()
            price_value = _safe_float(price, default=0.0)

            if outcome_name == "yes":
                yes_price = price_value
            elif outcome_name == "no":
                no_price = price_value

    return {
        "id": raw.get("id"),
        "question": raw.get("question"),
        "slug": raw.get("slug"),
        "active": bool(raw.get("active", False)),
        "closed": bool(raw.get("closed", False)),
        "accepting_orders": bool(raw.get("acceptingOrders", False)),
        "yes_price": yes_price,
        "no_price": no_price,
        "volume": _safe_float(raw.get("volume"), default=0.0),
        "liquidity": _safe_float(raw.get("liquidity"), default=0.0),
        "best_bid": _safe_float(raw.get("bestBid"), default=0.0),
        "best_ask": _safe_float(raw.get("bestAsk"), default=0.0),
        "spread": _safe_float(raw.get("spread"), default=0.0),
        "end_date": raw.get("endDate"),
    }


def score_market(market: dict, target_prob: float = 0.70) -> float:
    yes_price = market.get("yes_price") or 0.0
    volume = market.get("volume") or 0.0
    liquidity = market.get("liquidity") or 0.0
    spread = market.get("spread") or 0.0

    prob_score = max(0.0, 1.0 - abs(yes_price - target_prob) / 0.10)
    volume_score = min(volume / 1_000_000, 1.0)
    liquidity_score = min(liquidity / 50_000, 1.0)
    spread_score = max(0.0, 1.0 - (spread / 0.02))

    final_score = (
        prob_score * 0.35 +
        volume_score * 0.25 +
        liquidity_score * 0.25 +
        spread_score * 0.15
    )
    return round(final_score, 6)


def filter_candidate_markets(
    markets: list[dict],
    min_prob: float = 0.60,
    max_prob: float = 0.80,
    min_volume: float = 50000.0,
    max_spread: float = 0.02,
) -> list[dict]:
    candidates: list[dict] = []

    for raw in markets:
        market = normalize_market(raw)

        yes_price = market.get("yes_price")
        if yes_price is None:
            continue

        if not market["active"]:
            continue

        if market["closed"]:
            continue

        if not market["accepting_orders"]:
            continue

        if market["volume"] < min_volume:
            continue

        if market["spread"] <= 0:
            continue

        if market["spread"] > max_spread:
            continue

        if not (min_prob <= yes_price <= max_prob):
            continue

        market["score"] = score_market(market)
        candidates.append(market)

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )
    return candidates
