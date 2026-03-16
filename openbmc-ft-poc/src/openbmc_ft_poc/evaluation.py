"""
Evaluation utilities for openbmc-ft-poc.

Provides:
1. Dataset quality evaluation (pre-training)
2. Model output evaluation (post-training)

Scoring dimensions:
- Structure compliance
- Subsystem relevance
- Command usefulness
- Cautious missing-evidence behavior
- Debugging usefulness
"""

from __future__ import annotations

import re
from typing import Any

from .answer_formats import get_troubleshoot_sections
from .logging_utils import get_logger

logger = get_logger(__name__)

# Type alias placeholder (avoids dataclass import complexity)
_ExampleDict = dict

# Debug pattern keywords for relevance scoring
_SUBSYSTEM_KEYWORDS = {
    "ipmi": ["ipmitool", "ipmid", "ipmi", "KCS", "RMCP"],
    "redfish": ["redfish", "bmcweb", "curl", "HTTP", "Redfish"],
    "dbus": ["busctl", "ObjectMapper", "xyz.openbmc_project", "D-Bus"],
    "sensors": ["sensor", "hwmon", "entity-manager", "sysfs"],
    "services": ["systemctl", "journalctl", "service", "unit"],
    "logging": ["phosphor-logging", "event log", "SEL", "callout"],
    "boot": ["boot", "POST", "BIOS", "BootProgress", "state manager"],
}

_COMMAND_RE = re.compile(
    r"```|systemctl|journalctl|busctl|ipmitool|curl|bitbake|cat /|ls /",
    re.IGNORECASE,
)
_MISSING_EVIDENCE_RE = re.compile(
    r"missing evidence|need.*log|share.*output|without.*output|insufficient",
    re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(
    r"\*\*Confidence\*\*|Confidence.*?(Low|Medium|High)",
    re.IGNORECASE | re.DOTALL,
)
_UNSUPPORTED_CLAIM_RE = re.compile(
    r"the root cause is|definitely caused by|confirmed.*is|it is definitely",
    re.IGNORECASE,
)


def score_example(example: dict[str, Any]) -> dict[str, float]:
    """
    Score a single training example on multiple dimensions.

    Returns dict of scores (0.0 to 1.0 per dimension).
    """
    output = example.get("output", "")
    metadata = example.get("metadata", {})
    subsystem = metadata.get("subsystem", "")
    pattern = metadata.get("pattern", "")

    scores: dict[str, float] = {}

    # 1. Structure compliance
    sections = get_troubleshoot_sections()
    present = sum(1 for s in sections if s.lower() in output.lower())
    scores["structure_compliance"] = round(present / len(sections), 2)

    # 2. Command usefulness
    cmd_matches = len(_COMMAND_RE.findall(output))
    scores["command_usefulness"] = min(1.0, round(cmd_matches / 4, 2))  # 4 commands = 1.0

    # 3. Missing evidence behavior
    scores["missing_evidence_behavior"] = (
        1.0 if _MISSING_EVIDENCE_RE.search(output) else 0.0
    )

    # 4. Confidence stated
    scores["confidence_stated"] = (
        1.0 if _CONFIDENCE_RE.search(output) else 0.0
    )

    # 5. No unsupported claims
    scores["no_unsupported_claims"] = (
        0.0 if _UNSUPPORTED_CLAIM_RE.search(output) else 1.0
    )

    # 6. Subsystem relevance
    scores["subsystem_relevance"] = _score_subsystem_relevance(output, subsystem)

    # 7. Output length quality (penalize very short or very long)
    words = len(output.split())
    if words < 50:
        scores["length_quality"] = 0.0
    elif words < 100:
        scores["length_quality"] = 0.5
    elif words <= 600:
        scores["length_quality"] = 1.0
    else:
        scores["length_quality"] = 0.8  # slight penalty for very long

    # Overall score: weighted average
    weights = {
        "structure_compliance": 0.25,
        "command_usefulness": 0.20,
        "missing_evidence_behavior": 0.15,
        "confidence_stated": 0.10,
        "no_unsupported_claims": 0.10,
        "subsystem_relevance": 0.10,
        "length_quality": 0.10,
    }
    scores["overall"] = round(
        sum(scores[k] * w for k, w in weights.items()), 3
    )
    return scores


def _score_subsystem_relevance(output: str, subsystem: str) -> float:
    """Score whether the output mentions keywords relevant to the subsystem."""
    if not subsystem:
        return 0.5  # neutral if no subsystem specified

    output_lower = output.lower()
    keywords = _SUBSYSTEM_KEYWORDS.get(subsystem.split("-")[-1].lower(), [])
    if not keywords:
        return 0.5

    hits = sum(1 for kw in keywords if kw.lower() in output_lower)
    return min(1.0, round(hits / 2, 2))  # 2+ keyword hits = 1.0


def evaluate_dataset(
    examples: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Evaluate an entire dataset's quality.

    Returns aggregate statistics.
    """
    if not examples:
        return {"error": "empty dataset"}

    all_scores: list[dict[str, float]] = []
    for ex in examples:
        all_scores.append(score_example(ex))

    dimensions = [
        "structure_compliance", "command_usefulness",
        "missing_evidence_behavior", "confidence_stated",
        "no_unsupported_claims", "subsystem_relevance",
        "length_quality", "overall",
    ]

    averages = {}
    for dim in dimensions:
        vals = [s[dim] for s in all_scores]
        averages[f"avg_{dim}"] = round(sum(vals) / len(vals), 3)

    # Distribution of overall scores
    bins = {"excellent_0.8+": 0, "good_0.6-0.8": 0, "fair_0.4-0.6": 0, "poor_<0.4": 0}
    for s in all_scores:
        v = s["overall"]
        if v >= 0.8:
            bins["excellent_0.8+"] += 1
        elif v >= 0.6:
            bins["good_0.6-0.8"] += 1
        elif v >= 0.4:
            bins["fair_0.4-0.6"] += 1
        else:
            bins["poor_<0.4"] += 1

    return {
        "n_examples": len(examples),
        **averages,
        "score_distribution": bins,
    }


def print_eval_report(report: dict[str, Any]) -> None:
    """Print a formatted evaluation report."""
    print("\n" + "=" * 60)
    print("  OpenBMC FT PoC — Dataset Quality Evaluation")
    print("=" * 60)
    print(f"  Examples evaluated: {report.get('n_examples', 0)}")
    print()
    print("  Average scores:")

    dim_labels = {
        "avg_structure_compliance": "Structure compliance",
        "avg_command_usefulness": "Command usefulness",
        "avg_missing_evidence_behavior": "Missing evidence behavior",
        "avg_confidence_stated": "Confidence stated",
        "avg_no_unsupported_claims": "No unsupported claims",
        "avg_subsystem_relevance": "Subsystem relevance",
        "avg_length_quality": "Length quality",
        "avg_overall": "OVERALL",
    }
    for key, label in dim_labels.items():
        val = report.get(key, 0)
        bar = "█" * int(val * 20)
        print(f"    {label:<30} {val:.3f}  {bar}")

    if "score_distribution" in report:
        print()
        print("  Score distribution:")
        for bucket, cnt in report["score_distribution"].items():
            print(f"    {bucket:<20} {cnt}")

    print("=" * 60 + "\n")
