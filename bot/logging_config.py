# bot/logging_config.py
"""
Logging configuration for the Binance Futures trading bot.
Sets up both file-based and console logging with structured formatting.
"""

import logging
import os
from datetime import datetime


def setup_logging(log_dir: str = "logs") -> logging.Logger:
    """
    Configure and return the root logger for the trading bot.

    Creates a timestamped log file in the specified directory and
    attaches both a file handler (DEBUG+) and a console handler (INFO+).

    Args:
        log_dir: Directory where log files will be stored. Created if absent.

    Returns:
        Configured Logger instance named 'trading_bot'.
    """
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"trading_bot_{timestamp}.log")

    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if setup_logging is called more than once
    if logger.handlers:
        return logger

    # ── File handler: captures DEBUG and above ──────────────────────────────
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # ── Console handler: captures INFO and above ────────────────────────────
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging initialised → %s", log_filename)
    return logger
