from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


SNAPSHOT_DIR = Path("data/snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_compact() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def write_snapshot(payload: dict[str, Any], prefix: str = "market_snapshot") -> str:
    timestamp = utc_now_compact()
    file_path = SNAPSHOT_DIR / f"{prefix}_{timestamp}.json"

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return str(file_path)
