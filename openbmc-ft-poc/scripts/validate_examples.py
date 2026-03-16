#!/usr/bin/env python3
"""
Validate generated SFT examples.

Applies strict quality rules and outputs valid/rejected JSONL.

Usage:
    python3 scripts/validate_examples.py [--input path/to/examples.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.dataset_builder import read_jsonl, write_jsonl_with_metadata
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.validators import validate_batch

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SFT examples")
    parser.add_argument(
        "--input", default=None,
        help="Input JSONL path (default: data/intermediate/examples/generated_examples.jsonl)"
    )
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    input_path = Path(args.input) if args.input else (
        cfg.data_intermediate / "examples" / "generated_examples.jsonl"
    )

    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        logger.info("Run 'make generate' first")
        return 1

    examples = read_jsonl(input_path)
    logger.info(f"Loaded {len(examples)} examples from {input_path}")

    validation_cfg = cfg.settings["dataset"]["validation"]
    valid, rejected = validate_batch(
        examples,
        min_output_words=validation_cfg.get("min_output_words", 60),
        min_instruction_words=validation_cfg.get("min_instruction_words", 8),
    )

    out_dir = cfg.data_intermediate / "examples"

    valid_path = out_dir / "valid_examples.jsonl"
    rejected_path = out_dir / "rejected_examples.jsonl"

    write_jsonl_with_metadata(valid, valid_path)
    write_jsonl_with_metadata(rejected, rejected_path)

    print(f"\nValidation results:")
    print(f"  Valid:    {len(valid)} → {valid_path}")
    print(f"  Rejected: {len(rejected)} → {rejected_path}")
    print(f"  Rate:     {len(rejected)/(len(examples) or 1)*100:.1f}% rejected")

    if rejected:
        from collections import Counter
        reasons = Counter()
        for ex in rejected:
            for r in ex.get("rejection_reasons", ["unknown"]):
                reasons[r.split(":")[0].strip()] += 1
        print("\n  Top rejection reasons:")
        for reason, count in reasons.most_common(10):
            print(f"    {reason:<40} {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
