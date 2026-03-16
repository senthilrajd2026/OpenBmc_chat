#!/usr/bin/env python3
"""
Parse systemd service unit files from OpenBMC repos.

Outputs service signal JSONL to data/intermediate/services/.

Usage:
    python3 scripts/parse_services.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.repo_mining import extract_service_units

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    cfg = get_config()
    cfg.ensure_dirs()
    out_dir = cfg.data_intermediate / "services"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for repo_cfg in cfg.repos:
        if not repo_cfg.get("parse_services", False):
            continue

        repo_path = cfg.project_root / repo_cfg["local_path"]
        if not repo_path.exists():
            logger.warning(f"Repo not found: {repo_path}")
            continue

        services = extract_service_units(repo_path)
        out_path = out_dir / f"services_{repo_cfg['id']}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for svc in services:
                fh.write(json.dumps(svc, ensure_ascii=False) + "\n")

        logger.info(f"Wrote {len(services)} service signals to {out_path}")
        total += len(services)

    print(f"\nTotal service signals: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
