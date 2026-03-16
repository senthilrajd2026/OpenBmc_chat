"""Tests for the dedupe module."""

import pytest
from src.openbmc_ft_poc.dedupe import deduplicate, exact_dedup, tfidf_dedup


def make_example(instruction: str, output: str = "some output") -> dict:
    return {"instruction": instruction, "input": "", "output": output}


class TestExactDedup:
    def test_removes_exact_duplicates(self):
        examples = [
            make_example("How do I check the service status?"),
            make_example("How do I check the service status?"),  # exact dup
            make_example("Different question about sensors"),
        ]
        result = exact_dedup(examples)
        assert len(result) == 2

    def test_case_insensitive_dedup(self):
        examples = [
            make_example("How do I check the SERVICE STATUS?"),
            make_example("how do i check the service status?"),  # same after lowercasing
        ]
        result = exact_dedup(examples)
        assert len(result) == 1

    def test_unique_examples_preserved(self):
        examples = [
            make_example("Question one about IPMI"),
            make_example("Question two about sensors"),
            make_example("Question three about D-Bus"),
        ]
        result = exact_dedup(examples)
        assert len(result) == 3

    def test_empty_input(self):
        assert exact_dedup([]) == []

    def test_single_example(self):
        examples = [make_example("Single question")]
        result = exact_dedup(examples)
        assert len(result) == 1


class TestTfidfDedup:
    def test_removes_near_duplicates(self):
        # Use very similar sentences that should score high similarity
        examples = [
            make_example("How do I check the phosphor-logging service failure on OpenBMC?"),
            make_example("How do I check the phosphor-logging service failure on OpenBMC system?"),  # near dup
            make_example("What are the sensor D-Bus paths in OpenBMC?"),  # clearly different
        ]
        result = tfidf_dedup(examples, threshold=0.90)
        # Should have removed the near-dup
        assert len(result) <= 2

    def test_keeps_different_examples(self):
        examples = [
            make_example("Why is phosphor-logging service failing to start?"),
            make_example("How do I inspect sensor values via busctl on OpenBMC?"),
            make_example("What does ObjectMapper do when a service registers a D-Bus path?"),
        ]
        result = tfidf_dedup(examples, threshold=0.90)
        assert len(result) == 3

    def test_empty_input(self):
        assert tfidf_dedup([]) == []

    def test_single_example(self):
        examples = [make_example("Single question about OpenBMC")]
        result = tfidf_dedup(examples, threshold=0.90)
        assert len(result) == 1

    def test_threshold_100_keeps_all(self):
        """Threshold of 1.0 means exact-only similarity; should keep all near-dups."""
        examples = [
            make_example("How do I debug a failed phosphor-ipmi service?"),
            make_example("How to debug a failed phosphor-ipmi-host?"),
        ]
        result = tfidf_dedup(examples, threshold=1.0)
        assert len(result) == 2


class TestDeduplicate:
    def test_full_pipeline(self):
        examples = [
            make_example("How do I check the service status?"),
            make_example("How do I check the service status?"),  # exact dup
            make_example("Why is phosphor-logging service failing?"),
            make_example("Why is phosphor-logging service failing to start?"),  # near dup
            make_example("Completely different question about host power state"),
        ]
        result = deduplicate(examples, similarity_threshold=0.85)
        # Should have removed at least the exact dup
        assert len(result) < len(examples)
        assert len(result) >= 2

    def test_preserves_metadata(self):
        examples = [
            {
                "instruction": "Unique question about OpenBMC sensors",
                "input": "",
                "output": "some output",
                "metadata": {"pattern": "sensor_debug"},
            }
        ]
        result = deduplicate(examples)
        assert len(result) == 1
        assert result[0]["metadata"]["pattern"] == "sensor_debug"
