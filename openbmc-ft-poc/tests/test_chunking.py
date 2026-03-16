"""Tests for the chunking module."""

import pytest
from src.openbmc_ft_poc.chunking import (
    Chunk,
    infer_patterns,
    infer_subsystem,
    split_by_headings,
)

SAMPLE_DOC = """\
# phosphor-logging Overview

phosphor-logging provides event logging for OpenBMC.
It exposes the xyz.openbmc_project.Logging D-Bus interface.

## Service Failure

When phosphor-logging fails, events are not persisted.
Check the service with systemctl status and journalctl.

### Common Errors

Error: Failed to persist event log entry
This usually means the storage path is full or unmounted.

## D-Bus Interface

The interface is xyz.openbmc_project.Logging.
Use busctl to inspect it.
"""

SAMPLE_SUBSYSTEMS = [
    {"id": "phosphor-logging", "aliases": ["phosphor-logging", "event log", "Logging", "SEL"]},
    {"id": "phosphor-ipmi", "aliases": ["ipmid", "ipmitool", "IPMI"]},
    {"id": "bmcweb", "aliases": ["bmcweb", "redfish", "Redfish"]},
]

SAMPLE_PATTERNS = [
    {
        "id": "service_state_debug",
        "keywords": ["service failed", "systemctl", "journalctl", "inactive"],
    },
    {
        "id": "dbus_lookup_debug",
        "keywords": ["busctl", "ObjectMapper", "xyz.openbmc_project", "dbus"],
    },
    {
        "id": "event_logging_debug",
        "keywords": ["event log", "phosphor-logging", "logging", "SEL"],
    },
]


class TestSplitByHeadings:
    def test_basic_split(self):
        chunks = split_by_headings(
            SAMPLE_DOC,
            source_id="test::doc",
            repo="test-repo",
            path="README.md",
        )
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_has_required_fields(self):
        chunks = split_by_headings(
            SAMPLE_DOC,
            source_id="test::doc",
            repo="test-repo",
            path="README.md",
        )
        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.source_id == "test::doc"
            assert chunk.repo == "test-repo"
            assert chunk.path == "README.md"
            assert isinstance(chunk.content, str)
            assert chunk.tokens_est >= 0

    def test_headings_are_preserved(self):
        chunks = split_by_headings(
            SAMPLE_DOC,
            source_id="test::doc",
            repo="test-repo",
            path="README.md",
        )
        headings = [c.heading for c in chunks if c.heading]
        assert len(headings) >= 2
        # Should contain some of our section headings
        all_headings = " ".join(headings).lower()
        assert any(kw in all_headings for kw in ["phosphor", "service", "d-bus", "errors"])

    def test_empty_document(self):
        chunks = split_by_headings(
            "",
            source_id="test::empty",
            repo="test",
            path="empty.md",
        )
        # Empty doc should return no chunks or one empty chunk
        assert isinstance(chunks, list)

    def test_document_without_headings(self):
        # Use enough content to exceed min_tokens (default 30)
        plain_text = "This is plain text. " * 20 + "\nNo headings here. " * 10
        chunks = split_by_headings(
            plain_text,
            source_id="test::plain",
            repo="test",
            path="plain.txt",
            min_tokens=5,  # low min for this test
        )
        assert len(chunks) >= 1

    def test_max_tokens_respected(self):
        # Build a doc with multiple paragraphs, each ~30 words
        paragraphs = ["This is paragraph content about OpenBMC service debugging. " * 3
                      for _ in range(8)]
        long_section = "\n\n".join(paragraphs)
        doc = f"# Big Section\n\n{long_section}"
        chunks = split_by_headings(
            doc,
            source_id="test::long",
            repo="test",
            path="long.md",
            max_tokens=50,
            min_tokens=5,
        )
        # Should produce more than one chunk (multiple paragraphs)
        assert len(chunks) > 1

    def test_chunk_to_dict_roundtrip(self):
        chunks = split_by_headings(
            SAMPLE_DOC,
            source_id="test::doc",
            repo="test-repo",
            path="README.md",
        )
        for chunk in chunks:
            d = chunk.to_dict()
            restored = Chunk.from_dict(d)
            assert restored.chunk_id == chunk.chunk_id
            assert restored.content == chunk.content


class TestInferSubsystem:
    def test_logging_subsystem_detected(self):
        text = "phosphor-logging provides event log. xyz.openbmc_project.Logging interface."
        result = infer_subsystem(text, SAMPLE_SUBSYSTEMS)
        assert result == "phosphor-logging"

    def test_ipmi_subsystem_detected(self):
        text = "ipmitool sensor list | grep Fan"
        result = infer_subsystem(text, SAMPLE_SUBSYSTEMS)
        assert result == "phosphor-ipmi"

    def test_no_match_returns_empty(self):
        text = "completely unrelated content with no keywords"
        result = infer_subsystem(text, SAMPLE_SUBSYSTEMS)
        assert result == ""

    def test_empty_subsystems_list(self):
        result = infer_subsystem("ipmi busctl logging", [])
        assert result == ""


class TestInferPatterns:
    def test_service_debug_pattern(self):
        text = "systemctl status phosphor-logging.service journalctl"
        result = infer_patterns(text, SAMPLE_PATTERNS)
        assert "service_state_debug" in result

    def test_dbus_debug_pattern(self):
        text = "busctl call xyz.openbmc_project.ObjectMapper introspect"
        result = infer_patterns(text, SAMPLE_PATTERNS)
        assert "dbus_lookup_debug" in result

    def test_multiple_patterns(self):
        text = "systemctl status && busctl tree xyz.openbmc_project.Logging"
        result = infer_patterns(text, SAMPLE_PATTERNS)
        assert len(result) >= 2

    def test_no_match_returns_empty(self):
        text = "completely irrelevant content with nothing matching"
        result = infer_patterns(text, SAMPLE_PATTERNS)
        assert result == []
