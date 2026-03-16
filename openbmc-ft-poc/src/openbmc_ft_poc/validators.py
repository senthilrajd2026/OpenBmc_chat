"""
Training example validation for openbmc-ft-poc.

Enforces strict quality rules:
- Structured format compliance
- Minimum length requirements
- Required sections present
- Commands/checks present when expected
- Confidence stated
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_formats import get_explain_sections, get_troubleshoot_sections
from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single training example."""

    valid: bool
    reasons: list[str] = field(default_factory=list)

    def add_failure(self, reason: str) -> None:
        self.valid = False
        self.reasons.append(reason)


# Minimum word counts
MIN_OUTPUT_WORDS = 60
MIN_INSTRUCTION_WORDS = 8

# Patterns that indicate commands/checks are present
_COMMAND_PATTERN = re.compile(
    r"```|systemctl|journalctl|busctl|ipmitool|curl|bitbake|busctl|cat /|ls /",
    re.IGNORECASE,
)

# Confidence pattern
_CONFIDENCE_PATTERN = re.compile(
    r"\*\*Confidence\*\*|\bConfidence\b.*?(Low|Medium|High)",
    re.IGNORECASE | re.DOTALL,
)

# Generic phrases that indicate a low-quality output
_GENERIC_PATTERNS = [
    r"OpenBMC is an open source",
    r"This is a complex topic",
    r"There are many ways to",
    r"It depends on the situation",
    r"I recommend reading the documentation",
    r"Please consult the official",
]


def validate_example(
    example: dict[str, Any],
    min_output_words: int = MIN_OUTPUT_WORDS,
    min_instruction_words: int = MIN_INSTRUCTION_WORDS,
) -> ValidationResult:
    """
    Validate a single training example.

    Args:
        example: Dict with instruction, input, output keys
        min_output_words: Minimum word count for output
        min_instruction_words: Minimum word count for instruction

    Returns:
        ValidationResult with valid flag and failure reasons
    """
    result = ValidationResult(valid=True)

    instruction = example.get("instruction", "")
    output = example.get("output", "")
    metadata = example.get("metadata", {})
    pattern = metadata.get("pattern", "")

    # ----------------------------------------------------------------
    # Basic presence checks
    # ----------------------------------------------------------------
    if not instruction or not instruction.strip():
        result.add_failure("missing_instruction")
        return result

    if not output or not output.strip():
        result.add_failure("missing_output")
        return result

    # ----------------------------------------------------------------
    # Length checks
    # ----------------------------------------------------------------
    instr_words = len(instruction.split())
    output_words = len(output.split())

    if instr_words < min_instruction_words:
        result.add_failure(
            f"instruction_too_short ({instr_words} words, min {min_instruction_words})"
        )

    if output_words < min_output_words:
        result.add_failure(
            f"output_too_short ({output_words} words, min {min_output_words})"
        )

    # ----------------------------------------------------------------
    # Format compliance
    # ----------------------------------------------------------------
    is_insufficient = pattern == "insufficient_evidence"
    is_explain = _is_explain_answer(output)

    if is_explain:
        _check_sections(output, get_explain_sections(), result)
    else:
        _check_sections(output, get_troubleshoot_sections(), result)

    # ----------------------------------------------------------------
    # Commands/checks required for non-explanation, non-insufficient answers
    # ----------------------------------------------------------------
    if not is_explain and not is_insufficient:
        if not _COMMAND_PATTERN.search(output):
            result.add_failure(
                "no_commands_when_expected: troubleshoot answer has no commands or checks"
            )

    # ----------------------------------------------------------------
    # For insufficient_evidence: must ask for specific info
    # ----------------------------------------------------------------
    if is_insufficient:
        if "missing evidence" not in output.lower() and "missing" not in output.lower():
            result.add_failure("insufficient_evidence_missing_request")

    # ----------------------------------------------------------------
    # Confidence required
    # ----------------------------------------------------------------
    if not _CONFIDENCE_PATTERN.search(output):
        result.add_failure("missing_confidence_section")

    # ----------------------------------------------------------------
    # Generic output detection
    # ----------------------------------------------------------------
    for gp in _GENERIC_PATTERNS:
        if re.search(gp, output, re.IGNORECASE):
            result.add_failure(f"generic_output_pattern: '{gp[:40]}'")
            break

    return result


def _check_sections(
    output: str,
    required_sections: list[str],
    result: ValidationResult,
) -> None:
    """Check that required section headers are present in the output."""
    output_lower = output.lower()
    for section in required_sections:
        if section.lower() not in output_lower:
            result.add_failure(f"missing_required_section: '{section}'")


def _is_explain_answer(output: str) -> bool:
    """Detect if an output uses the explain format rather than troubleshoot."""
    lower = output.lower()
    return "**explanation**" in lower or "explanation\n" in lower


def validate_batch(
    examples: list[dict[str, Any]],
    min_output_words: int = MIN_OUTPUT_WORDS,
    min_instruction_words: int = MIN_INSTRUCTION_WORDS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate a list of examples.

    Returns:
        Tuple of (valid_examples, rejected_examples)
        Rejected examples have a 'rejection_reasons' key added.
    """
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for ex in examples:
        result = validate_example(
            ex,
            min_output_words=min_output_words,
            min_instruction_words=min_instruction_words,
        )
        if result.valid:
            valid.append(ex)
        else:
            rejected_ex = {**ex, "rejection_reasons": result.reasons}
            rejected.append(rejected_ex)

    logger.info(
        f"Validation: {len(valid)} valid, {len(rejected)} rejected "
        f"({len(rejected)/(len(examples) or 1)*100:.1f}% rejection rate)"
    )
    return valid, rejected
