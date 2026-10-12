import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE  = LOG_DIR / "app.log"

_CONSOLE_FMT = "[{asctime}] {levelname:<8} {name}:{lineno} — {message}"
_FILE_FMT    = "{asctime} | {levelname:<8} | {name}:{lineno} | {message}"


def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, style="{", datefmt="%H:%M:%S"))
    logger.addHandler(console)

    file = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(logging.Formatter(_FILE_FMT, style="{", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(file)

    logger.propagate = False
    return logger