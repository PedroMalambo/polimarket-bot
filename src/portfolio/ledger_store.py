from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PORTFOLIO_DIR = Path("data/portfolio")
PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)

POSITIONS_FILE = PORTFOLIO_DIR / "positions.json"
TRADES_FILE = PORTFOLIO_DIR / "trades.json"


def _ensure_json_file(path: Path, default: Any) -> None:
    if not path.exists():
        with path.open("w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)


def ensure_ledger_files() -> None:
    _ensure_json_file(POSITIONS_FILE, [])
    _ensure_json_file(TRADES_FILE, [])


def load_json(path: Path) -> list[dict]:
    ensure_ledger_files()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []


def save_json(path: Path, payload: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_positions() -> list[dict]:
    return load_json(POSITIONS_FILE)


def save_positions(positions: list[dict]) -> None:
    save_json(POSITIONS_FILE, positions)


def load_trades() -> list[dict]:
    return load_json(TRADES_FILE)


def save_trades(trades: list[dict]) -> None:
    save_json(TRADES_FILE, trades)


def find_open_position_by_market_id(market_id: str) -> dict | None:
    positions = load_positions()
    for position in positions:
        if position.get("market_id") == market_id and position.get("status") == "OPEN":
            return position
    return None
