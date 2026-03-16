#!/usr/bin/env python3
"""
Consolidate and re-index all intermediate chunks for generation.

Reads all chunk JSONL files from data/intermediate/chunks/,
applies consistent IDs, and outputs combined chunks JSONL.

Usage:
    python3 scripts/chunk_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    cfg = get_config()
    cfg.ensure_dirs()

    chunks_dir = cfg.data_intermediate / "chunks"
    out_path = cfg.data_intermediate / "all_chunks.jsonl"

    chunk_files = sorted(chunks_dir.glob("*.jsonl")) if chunks_dir.exists() else []
    if not chunk_files:
        logger.warning("No chunk files found in data/intermediate/chunks/")
        logger.info("Run 'make parse' first to generate chunks")
        return 0

    total = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk_file in chunk_files:
            count = 0
            with chunk_file.open("r", encoding="utf-8") as cfh:
                for line in cfh:
                    line = line.strip()
                    if line:
                        fh.write(line + "\n")
                        count += 1
            logger.info(f"  {chunk_file.name}: {count} chunks")
            total += count

    logger.info(f"Consolidated {total} chunks to {out_path}")
    print(f"\nTotal consolidated chunks: {total}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
