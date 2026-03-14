from __future__ import annotations

import json
import urllib.error
import urllib.request

from src.config.settings import get_settings
from src.monitoring.logger import app_logger


def is_telegram_enabled() -> bool:
    settings = get_settings()
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def send_telegram_message(message: str) -> bool:
    settings = get_settings()

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        app_logger.info("TELEGRAM_NOT_CONFIGURED=skip")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = getattr(response, "status", None)
            app_logger.info(f"TELEGRAM_SEND_OK=True | status_code={status_code}")
        return True
    except urllib.error.HTTPError as exc:
        app_logger.warning(
            f"TELEGRAM_SEND_OK=False | http_status={exc.code} | error={exc.reason}"
        )
        return False
    except Exception as exc:
        app_logger.warning(f"TELEGRAM_SEND_OK=False | error={exc}")
        return False
