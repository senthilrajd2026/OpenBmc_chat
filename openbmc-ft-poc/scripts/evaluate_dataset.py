#!/usr/bin/env python3
"""
Evaluate dataset quality before training.

Scores examples on structure compliance, command usefulness,
missing-evidence behavior, and other dimensions.

Usage:
    python3 scripts/evaluate_dataset.py [--input data/train.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.dataset_builder import read_jsonl
from openbmc_ft_poc.evaluation import evaluate_dataset, print_eval_report
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate dataset quality")
    parser.add_argument("--input", default=None, help="Input JSONL path")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    cfg = get_config()

    input_path = Path(args.input) if args.input else cfg.train_output
    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        return 1

    examples = read_jsonl(input_path)
    logger.info(f"Evaluating {len(examples)} examples from {input_path}")

    report = evaluate_dataset(examples)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_eval_report(report)

    # Save report
    report_path = cfg.data_reports / "eval_quality_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    logger.info(f"Report saved to {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
