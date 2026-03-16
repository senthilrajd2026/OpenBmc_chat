#!/usr/bin/env python3
"""
Summarize OpenBMC build logs to identify blockers.

Usage:
    python3 scripts/summarize_build_logs.py [--log-dir data/logs]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

_ERROR_PATTERNS = [
    (re.compile(r"ERROR: (.+)", re.IGNORECASE), "ERROR"),
    (re.compile(r"FAILED: (.+)", re.IGNORECASE), "FAILED"),
    (re.compile(r"fatal error: (.+)", re.IGNORECASE), "FATAL"),
    (re.compile(r"undefined reference to (.+)", re.IGNORECASE), "LINKER"),
    (re.compile(r"BitBake Build Failure", re.IGNORECASE), "BITBAKE"),
    (re.compile(r"do_\w+: FAILED", re.IGNORECASE), "TASK_FAILED"),
]


def summarize_log_file(log_path: Path) -> dict:
    """Extract error and failure lines from a build log."""
    if not log_path.exists():
        return {"path": str(log_path), "errors": [], "error_count": 0}

    text = log_path.read_text(encoding="utf-8", errors="replace")
    errors: list[dict] = []

    for pattern, kind in _ERROR_PATTERNS:
        for m in pattern.finditer(text):
            errors.append({"kind": kind, "message": m.group(0)[:200]})

    return {
        "path": str(log_path),
        "errors": errors[:50],  # cap output
        "error_count": len(errors),
        "total_lines": text.count("\n"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize OpenBMC build logs")
    parser.add_argument("--log-dir", default="data/logs", help="Directory containing build logs")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        logger.warning(f"Log directory not found: {log_dir}")
        return 0

    log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("build_*.txt"))

    if not log_files:
        print(f"No log files found in {log_dir}")
        return 0

    for log_file in log_files:
        summary = summarize_log_file(log_file)
        print(f"\n{'='*60}")
        print(f"Log: {summary['path']}")
        print(f"Lines: {summary['total_lines']}, Errors found: {summary['error_count']}")
        if summary["errors"]:
            print("Top errors:")
            for err in summary["errors"][:10]:
                print(f"  [{err['kind']}] {err['message']}")
        else:
            print("No errors detected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
