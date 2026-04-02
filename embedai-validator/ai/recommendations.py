"""High-level recommendations derived from the full run summary.

This module produces a short human-readable recommendation block that appears
at the bottom of reports.  It complements the per-result suggestions from
rules.py with board-wide observations.
"""

from __future__ import annotations

from core.result_model import RunResult, Status


def build_summary_recommendations(run: RunResult) -> list[str]:
    """Return a list of board-wide recommendation strings."""
    recs: list[str] = []

    if run.summary.overall_status == Status.PASS:
        recs.append("All tested peripherals passed validation. Board appears healthy.")
        return recs

    if run.summary.failed > 0:
        recs.append(
            f"{run.summary.failed} test(s) failed. "
            "Review per-test suggestions and re-run after applying fixes."
        )

    if run.summary.errors > 0:
        recs.append(
            f"{run.summary.errors} test(s) encountered errors. "
            "Check tool availability and permissions, then re-run."
        )

    if run.summary.skipped == run.summary.total:
        recs.append(
            "All tests were skipped. "
            "Consider running with --mock to verify the framework, "
            "or install required Linux tools (i2c-tools, gpiod, etc.)."
        )
    elif run.summary.skipped > 0:
        skipped_ids = [r.test_id for r in run.results if r.status == Status.SKIP]
        recs.append(
            f"{run.summary.skipped} test(s) skipped: "
            + ", ".join(skipped_ids[:5])
            + ("…" if len(skipped_ids) > 5 else "")
        )

    if run.mock_mode:
        recs.append(
            "Run was executed in MOCK mode. "
            "Results reflect simulated behaviour, not real hardware."
        )

    return recs
