#!/usr/bin/env python3
"""
Split deduplicated examples into train/eval sets.

Outputs Axolotl-ready JSONL files: data/train.jsonl and data/eval.jsonl.
Also writes metadata JSONL and a summary report.

Usage:
    python3 scripts/split_dataset.py [--train-ratio 0.90]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.dataset_builder import (
    generate_report,
    print_report,
    read_jsonl,
    split_dataset,
    write_jsonl,
    write_jsonl_with_metadata,
)
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Split dataset into train/eval")
    parser.add_argument(
        "--train-ratio", type=float, default=None,
        help="Train fraction (default from config: 0.90)"
    )
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    input_path = cfg.data_intermediate / "examples" / "deduped_examples.jsonl"
    if not input_path.exists():
        # Fall back to valid_examples if deduped not available
        input_path = cfg.data_intermediate / "examples" / "valid_examples.jsonl"

    if not input_path.exists():
        logger.error(f"No examples found at {input_path}")
        logger.info("Run 'make generate && make validate && make dedupe' first")
        return 1

    examples = read_jsonl(input_path)
    logger.info(f"Loaded {len(examples)} examples from {input_path}")

    if len(examples) < 10:
        logger.warning(f"Very small dataset ({len(examples)} examples). This is a PoC — consider generating more.")

    train_ratio = args.train_ratio or cfg.settings["dataset"]["train_split"]
    train, eval_ = split_dataset(examples, train_ratio=train_ratio, seed=cfg.seed)

    # Write Axolotl-ready JSONL (no metadata)
    write_jsonl(train, cfg.train_output)
    write_jsonl(eval_, cfg.eval_output)

    # Write with-metadata versions for analysis
    write_jsonl_with_metadata(train, cfg.data_processed / "train_with_meta.jsonl")
    write_jsonl_with_metadata(eval_, cfg.data_processed / "eval_with_meta.jsonl")

    # Load rejected examples for the report
    rejected_path = cfg.data_intermediate / "examples" / "rejected_examples.jsonl"
    rejected = read_jsonl(rejected_path) if rejected_path.exists() else []

    # Generate and save report
    report = generate_report(train, eval_, rejected)
    print_report(report)

    report_path = cfg.data_reports / "dataset_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"Train: {cfg.train_output}")
    print(f"Eval:  {cfg.eval_output}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
