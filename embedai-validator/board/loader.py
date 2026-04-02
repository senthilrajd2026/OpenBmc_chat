"""Board profile YAML loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from board.schemas import BoardProfile
from utils.logger import get_logger

log = get_logger(__name__)


class BoardLoadError(Exception):
    """Raised when a board YAML cannot be parsed or validated."""


def load_board(path: Path) -> BoardProfile:
    """Load and validate a board profile from *path*.

    Raises BoardLoadError with a human-readable message on failure.
    """
    if not path.exists():
        raise BoardLoadError(f"Board profile not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BoardLoadError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise BoardLoadError(f"Board profile must be a YAML mapping, got {type(raw).__name__}")

    try:
        profile = BoardProfile.model_validate(raw)
    except ValidationError as exc:
        raise BoardLoadError(f"Board profile schema error in {path}:\n{exc}") from exc

    log.info(
        "Loaded board profile: [bold]%s[/bold] (rev %s)",
        profile.board.name,
        profile.board.revision or "?",
    )
    return profile
