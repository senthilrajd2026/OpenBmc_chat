"""Pydantic models for test results and validation runs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


class Evidence(BaseModel):
    """Raw evidence captured during a test (command output, file content, etc.)."""

    source: str  # e.g. "i2cdetect", "sysfs", "mock"
    data: str


class TestResult(BaseModel):
    """Single test execution result."""

    test_id: str
    plugin_name: str
    status: Status
    duration_ms: float = 0.0
    message: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    error_code: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0

    @classmethod
    def from_results(cls, results: list[TestResult]) -> "ValidationSummary":
        s = cls(total=len(results))
        for r in results:
            match r.status:
                case Status.PASS:
                    s.passed += 1
                case Status.FAIL:
                    s.failed += 1
                case Status.SKIP:
                    s.skipped += 1
                case Status.ERROR:
                    s.errors += 1
        return s

    @property
    def overall_status(self) -> Status:
        if self.errors > 0 or self.failed > 0:
            return Status.FAIL
        if self.skipped == self.total:
            return Status.SKIP
        return Status.PASS


class RunResult(BaseModel):
    """Top-level container for a complete validation run."""

    run_id: str
    board_name: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: ValidationSummary = Field(default_factory=ValidationSummary)
    results: list[TestResult] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    mock_mode: bool = False

    def finalize(self) -> None:
        self.finished_at = datetime.now()
        self.summary = ValidationSummary.from_results(self.results)
