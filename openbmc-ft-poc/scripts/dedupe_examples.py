#!/usr/bin/env python3
"""
Deduplicate validated SFT examples.

Removes exact and near-duplicate instructions using TF-IDF cosine similarity.

Usage:
    python3 scripts/dedupe_examples.py [--threshold 0.92]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.dataset_builder import read_jsonl, write_jsonl_with_metadata
from openbmc_ft_poc.dedupe import deduplicate
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate SFT examples")
    parser.add_argument(
        "--threshold", type=float, default=0.92,
        help="Cosine similarity threshold for near-duplicate detection (default: 0.92)"
    )
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    input_path = cfg.data_intermediate / "examples" / "valid_examples.jsonl"
    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        logger.info("Run 'make validate' first")
        return 1

    examples = read_jsonl(input_path)
    logger.info(f"Loaded {len(examples)} valid examples")

    deduped = deduplicate(examples, similarity_threshold=args.threshold)

    out_path = cfg.data_intermediate / "examples" / "deduped_examples.jsonl"
    write_jsonl_with_metadata(deduped, out_path)

    print(f"\nDeduplication: {len(examples)} → {len(deduped)} examples")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
