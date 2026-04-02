"""Structured logging setup for EmbedAI Validator."""

import logging
import sys
from pathlib import Path

from rich.logging import RichHandler


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with rich formatting."""
    return logging.getLogger(name)


def configure_logging(verbose: bool = False, log_file: Path | None = None) -> None:
    """Configure root logging with Rich console output and optional file sink."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = [
        RichHandler(
            level=level,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
        )
    ]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers,
        force=True,
    )
