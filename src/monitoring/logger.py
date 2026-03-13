import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

logger.add(
    LOG_DIR / "app.log",
    level="INFO",
    rotation="10 MB",
    retention=10,
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

app_logger = logger
