"""
Dataset builder for openbmc-ft-poc.

Combines validated, deduplicated examples into Axolotl-ready JSONL files.
Handles train/eval splitting with pattern/subsystem diversity preservation.
Generates summary reports.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .logging_utils import get_logger

logger = get_logger(__name__)


def split_dataset(
    examples: list[dict[str, Any]],
    train_ratio: float = 0.90,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Split examples into train and eval sets.

    Attempts to preserve diversity across patterns and subsystems
    by stratified sampling where possible.

    Args:
        examples: Full list of validated examples
        train_ratio: Fraction to use for training
        seed: Random seed for reproducibility

    Returns:
        Tuple of (train_examples, eval_examples)
    """
    if not examples:
        return [], []

    rng = random.Random(seed)

    # Group by pattern for stratified split
    by_pattern: dict[str, list[dict]] = {}
    for ex in examples:
        pattern = ex.get("metadata", {}).get("pattern", "unknown")
        by_pattern.setdefault(pattern, []).append(ex)

    train: list[dict[str, Any]] = []
    eval_: list[dict[str, Any]] = []

    for pattern, group in by_pattern.items():
        shuffled = group.copy()
        rng.shuffle(shuffled)
        n_train = max(1, int(len(shuffled) * train_ratio))
        train.extend(shuffled[:n_train])
        eval_.extend(shuffled[n_train:])

    # Shuffle final sets
    rng.shuffle(train)
    rng.shuffle(eval_)

    logger.info(
        f"Dataset split: {len(train)} train, {len(eval_)} eval "
        f"(ratio={train_ratio:.0%})"
    )
    return train, eval_


def write_jsonl(examples: list[dict[str, Any]], path: Path) -> None:
    """Write examples to a JSONL file in Axolotl alpaca format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            # Write only the fields Axolotl expects
            record = {
                "instruction": ex.get("instruction", ""),
                "input": ex.get("input", ""),
                "output": ex.get("output", ""),
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {len(examples)} examples to {path}")


def write_jsonl_with_metadata(examples: list[dict[str, Any]], path: Path) -> None:
    """Write examples including metadata (for analysis, not training)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {len(examples)} examples (with metadata) to {path}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dicts."""
    if not path.exists():
        return []
    examples = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    examples.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning(f"Skipping malformed JSON line: {exc}")
    return examples


def generate_report(
    train: list[dict[str, Any]],
    eval_: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate a quality and diversity report for the dataset.

    Returns a dict suitable for JSON serialization.
    """
    all_valid = train + eval_

    def _counter(field: str) -> dict[str, int]:
        return dict(Counter(
            ex.get("metadata", {}).get(field, "unknown") for ex in all_valid
        ))

    def _avg_words(field: str) -> float:
        lengths = [len(ex.get(field, "").split()) for ex in all_valid]
        return round(sum(lengths) / len(lengths), 1) if lengths else 0.0

    # Count debug-oriented vs explanation-oriented
    debug_count = sum(
        1 for ex in all_valid
        if ex.get("metadata", {}).get("pattern", "") not in ("", "unknown")
        and "explain" not in ex.get("metadata", {}).get("pattern", "")
    )
    explain_count = len(all_valid) - debug_count

    rejection_reasons: dict[str, int] = {}
    for ex in rejected:
        for reason in ex.get("rejection_reasons", ["unknown"]):
            # Normalize reason key
            key = reason.split(":")[0].strip()
            rejection_reasons[key] = rejection_reasons.get(key, 0) + 1

    return {
        "total_valid": len(all_valid),
        "total_train": len(train),
        "total_eval": len(eval_),
        "total_rejected": len(rejected),
        "rejection_rate_pct": round(
            len(rejected) / (len(all_valid) + len(rejected)) * 100, 1
        ) if (all_valid or rejected) else 0.0,
        "by_pattern": _counter("pattern"),
        "by_subsystem": _counter("subsystem"),
        "by_source_type": _counter("source_type"),
        "avg_instruction_words": _avg_words("instruction"),
        "avg_output_words": _avg_words("output"),
        "debugging_pct": round(debug_count / len(all_valid) * 100, 1) if all_valid else 0.0,
        "explanation_pct": round(explain_count / len(all_valid) * 100, 1) if all_valid else 0.0,
        "rejection_reasons": rejection_reasons,
    }


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted dataset report to stdout."""
    print("\n" + "=" * 60)
    print("  OpenBMC FT PoC — Dataset Report")
    print("=" * 60)
    print(f"  Total valid:    {report['total_valid']}")
    print(f"  Train examples: {report['total_train']}")
    print(f"  Eval examples:  {report['total_eval']}")
    print(f"  Rejected:       {report['total_rejected']} ({report['rejection_rate_pct']}%)")
    print(f"  Avg instruction words: {report['avg_instruction_words']}")
    print(f"  Avg output words:      {report['avg_output_words']}")
    print(f"  Debugging-oriented:    {report['debugging_pct']}%")
    print(f"  Explanation-oriented:  {report['explanation_pct']}%")

    print("\n  Examples by pattern:")
    for pat, cnt in sorted(report["by_pattern"].items(), key=lambda x: -x[1]):
        print(f"    {pat:<35} {cnt}")

    print("\n  Examples by subsystem:")
    for sub, cnt in sorted(report["by_subsystem"].items(), key=lambda x: -x[1]):
        print(f"    {sub:<35} {cnt}")

    print("\n  Examples by source type:")
    for src, cnt in sorted(report["by_source_type"].items(), key=lambda x: -x[1]):
        print(f"    {src:<35} {cnt}")

    if report["rejection_reasons"]:
        print("\n  Rejection reasons:")
        for reason, cnt in sorted(report["rejection_reasons"].items(), key=lambda x: -x[1]):
            print(f"    {reason:<40} {cnt}")

    print("=" * 60 + "\n")
