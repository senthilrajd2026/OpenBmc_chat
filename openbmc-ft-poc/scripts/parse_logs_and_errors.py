#!/usr/bin/env python3
"""
Extract log/error strings from OpenBMC C++ source files.

Outputs JSONL to data/intermediate/log_strings/.

Usage:
    python3 scripts/parse_logs_and_errors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.repo_mining import extract_log_strings

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    cfg = get_config()
    cfg.ensure_dirs()
    out_dir = cfg.data_intermediate / "log_strings"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for repo_cfg in cfg.repos:
        repo_path = cfg.project_root / repo_cfg["local_path"]
        if not repo_path.exists():
            logger.warning(f"Repo not found: {repo_path}")
            continue

        signals = extract_log_strings(repo_path)
        out_path = out_dir / f"logs_{repo_cfg['id']}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for sig in signals:
                fh.write(json.dumps(sig, ensure_ascii=False) + "\n")

        logger.info(f"Wrote {len(signals)} log strings to {out_path}")
        total += len(signals)

    print(f"\nTotal log strings: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
