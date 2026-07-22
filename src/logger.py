"""
logger.py

Sets up a rotating file logger plus console output so pipeline runs leave
a durable, size-capped audit trail instead of an ever-growing log file.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str, log_path: str, level: str = "INFO",
                max_bytes: int = 1_000_000, backup_count: int = 3) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        # Avoid attaching duplicate handlers if this is called more than once
        # (e.g. imported by both the pipeline and a test module).
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
