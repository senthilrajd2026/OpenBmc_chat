"""JSON report exporter."""

from __future__ import annotations

import json
from pathlib import Path

from core.result_model import RunResult
from utils.logger import get_logger
from utils.paths import timestamped_path

log = get_logger(__name__)


def export_json(run: RunResult, path: Path | None = None) -> Path:
    """Serialise *run* to a timestamped JSON file and return its path."""
    out = path or timestamped_path("report", "json")
    data = json.loads(run.model_dump_json(indent=2))
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    log.info("JSON report saved → %s", out)
    return out
