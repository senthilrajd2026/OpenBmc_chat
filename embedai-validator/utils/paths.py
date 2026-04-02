"""Path helpers for EmbedAI Validator."""

from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
BOARDS_DIR = PROJECT_ROOT / "boards"


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def timestamped_path(prefix: str, suffix: str) -> Path:
    """Return output/<prefix>_YYYYMMDD_HHMMSS.<suffix>."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ensure_output_dir()
    return OUTPUT_DIR / f"{prefix}_{ts}.{suffix}"
