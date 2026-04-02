"""Validation context – shared state passed to every plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from board.schemas import BoardProfile


@dataclass
class ValidationContext:
    """Immutable-ish bag of context for a validation run."""

    profile: BoardProfile
    run_id: str
    mock_mode: bool = False
    suite: str | None = None          # e.g. "smoke", "full"
    output_dir: Path = Path("output")
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def board_name(self) -> str:
        return self.profile.board.name
