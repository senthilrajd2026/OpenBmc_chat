"""
Issue transformation for openbmc-ft-poc.

Normalizes GitHub issue records into intermediate training signals.
Detects debug patterns, subsystems, and extracts structured information.
"""

from __future__ import annotations

import re
from typing import Any

from .chunking import infer_patterns, infer_subsystem
from .logging_utils import get_logger

logger = get_logger(__name__)

# Command/output patterns that indicate concrete engineering evidence
_COMMAND_RE = re.compile(
    r"```(?:bash|shell|console|sh)?\n?(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JOURNALCTL_RE = re.compile(r"\bjournalctl\b", re.IGNORECASE)
_SYSTEMCTL_RE = re.compile(r"\bsystemctl\b", re.IGNORECASE)
_BUSCTL_RE = re.compile(r"\bbusctl\b", re.IGNORECASE)


def transform_issue(
    issue: dict[str, Any],
    debug_patterns: list[dict],
    subsystems: list[dict],
) -> dict[str, Any] | None:
    """
    Transform a normalized GitHub issue into an intermediate training signal.

    Args:
        issue: Normalized issue dict from github_client
        debug_patterns: Pattern definitions from dataset_rules.yaml
        subsystems: Subsystem definitions from dataset_rules.yaml

    Returns:
        Intermediate signal dict, or None if issue is unsuitable
    """
    title = issue.get("title", "").strip()
    body = issue.get("body", "").strip()
    full_text = f"{title}\n\n{body}"

    if not title or len(body) < 50:
        return None

    # Extract code blocks as evidence
    code_blocks = _COMMAND_RE.findall(full_text)
    has_commands = bool(
        code_blocks
        or _JOURNALCTL_RE.search(full_text)
        or _SYSTEMCTL_RE.search(full_text)
        or _BUSCTL_RE.search(full_text)
    )

    # Detect patterns and subsystem
    patterns = infer_patterns(full_text, debug_patterns)
    subsystem = infer_subsystem(full_text, subsystems)

    # Extract resolution signals from closed issues
    resolution_hint = _extract_resolution(body)

    return {
        "source_type": "github_issue",
        "source_id": issue["id"],
        "repo": issue["repo"],
        "issue_number": issue["number"],
        "title": title,
        "body_snippet": body[:1500],
        "has_commands": has_commands,
        "code_blocks": [cb[:400] for cb in code_blocks[:5]],
        "patterns": patterns,
        "subsystem": subsystem,
        "state": issue.get("state", ""),
        "labels": issue.get("labels", []),
        "resolution_hint": resolution_hint,
        "url": issue.get("url", ""),
    }


def _extract_resolution(body: str) -> str:
    """
    Attempt to extract resolution/fix information from issue body.

    Looks for common resolution markers.
    """
    resolution_markers = [
        "fix:", "fixed by", "resolved by", "solution:", "workaround:",
        "root cause:", "cause:", "the issue was", "it turned out",
        "the problem was", "this was caused by", "to fix this",
    ]
    lower = body.lower()
    best_start = -1
    best_marker = ""

    for marker in resolution_markers:
        idx = lower.rfind(marker)  # look near end of body
        if idx > best_start:
            best_start = idx
            best_marker = marker

    if best_start > 0:
        snippet = body[best_start:best_start + 500].strip()
        return snippet

    return ""


def transform_issues_batch(
    issues: list[dict[str, Any]],
    debug_patterns: list[dict],
    subsystems: list[dict],
) -> list[dict[str, Any]]:
    """
    Transform a list of GitHub issues into intermediate signals.

    Skips unsuitable issues and logs counts.
    """
    signals: list[dict[str, Any]] = []
    skipped = 0

    for issue in issues:
        signal = transform_issue(issue, debug_patterns, subsystems)
        if signal is not None:
            signals.append(signal)
        else:
            skipped += 1

    logger.info(
        f"Transformed {len(signals)} issues into signals "
        f"(skipped {skipped} unsuitable)"
    )
    return signals
