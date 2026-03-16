#!/usr/bin/env python3
"""
Environment check script for openbmc-ft-poc.

Detects WSL2 vs native Linux, hardware, GPU/CUDA,
and reports pipeline feasibility.

Usage:
    python3 scripts/check_env.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.env_detect import detect_environment, format_report
from openbmc_ft_poc.logging_utils import setup_logging

setup_logging()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check environment for openbmc-ft-poc")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    report = detect_environment()

    if args.json:
        # Serialize dataclass to dict
        import dataclasses
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(format_report(report))

    # Exit 0 if dataset generation is feasible; 1 otherwise
    return 0 if report.can_generate_dataset else 1


if __name__ == "__main__":
    sys.exit(main())
