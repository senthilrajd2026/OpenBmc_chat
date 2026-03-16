"""
Structured logging setup for openbmc-ft-poc.

Provides a consistent log format across all modules.
Supports both file and console output.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    name: str = "openbmc_ft_poc",
) -> logging.Logger:
    """
    Configure and return a logger.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to write log file
        name: Logger name

    Returns:
        Configured Logger instance
    """
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(console)

    # File handler (optional)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the openbmc_ft_poc namespace.

    Usage:
        logger = get_logger(__name__)
    """
    if not name.startswith("openbmc_ft_poc"):
        name = f"openbmc_ft_poc.{name}"
    return logging.getLogger(name)
