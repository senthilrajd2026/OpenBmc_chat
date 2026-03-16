#!/usr/bin/env python3
"""
Extract high-level repo metadata from cloned OpenBMC repos.

Outputs metadata JSON to data/intermediate/metadata/.

Usage:
    python3 scripts/parse_repo_metadata.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.repo_mining import extract_repo_metadata

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    cfg = get_config()
    cfg.ensure_dirs()
    out_dir = cfg.data_intermediate / "metadata"
    out_dir.mkdir(parents=True, exist_ok=True)

    for repo_cfg in cfg.repos:
        repo_path = cfg.project_root / repo_cfg["local_path"]
        if not repo_path.exists():
            logger.warning(f"Repo not found: {repo_path}")
            continue

        meta = extract_repo_metadata(repo_path)
        out_path = out_dir / f"meta_{repo_cfg['id']}.json"
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        logger.info(f"Saved metadata for {repo_cfg['id']} to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
