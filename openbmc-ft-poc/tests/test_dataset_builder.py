"""Tests for the dataset_builder module."""

import json
import tempfile
from pathlib import Path

import pytest
from src.openbmc_ft_poc.dataset_builder import (
    generate_report,
    read_jsonl,
    split_dataset,
    write_jsonl,
    write_jsonl_with_metadata,
)


def make_example(
    instruction: str = "Test instruction about OpenBMC service debug",
    output: str = "Test output",
    pattern: str = "service_state_debug",
    subsystem: str = "phosphor-ipmi",
    source_type: str = "doc_chunk",
) -> dict:
    return {
        "instruction": instruction,
        "input": "",
        "output": output,
        "metadata": {
            "pattern": pattern,
            "subsystem": subsystem,
            "source_type": source_type,
        },
    }


class TestSplitDataset:
    def test_basic_split(self):
        examples = [make_example(f"Question {i}") for i in range(100)]
        train, eval_ = split_dataset(examples, train_ratio=0.9, seed=42)
        assert len(train) + len(eval_) == 100
        assert len(train) >= 85  # roughly 90%

    def test_empty_input(self):
        train, eval_ = split_dataset([], train_ratio=0.9)
        assert train == []
        assert eval_ == []

    def test_reproducible_with_seed(self):
        examples = [make_example(f"Question {i}") for i in range(50)]
        train1, eval1 = split_dataset(examples, seed=42)
        train2, eval2 = split_dataset(examples, seed=42)
        assert [e["instruction"] for e in train1] == [e["instruction"] for e in train2]

    def test_different_seed_different_split(self):
        examples = [make_example(f"Question {i}") for i in range(50)]
        train1, _ = split_dataset(examples, seed=42)
        train2, _ = split_dataset(examples, seed=123)
        # Should be different orderings
        assert [e["instruction"] for e in train1] != [e["instruction"] for e in train2]

    def test_pattern_diversity_preserved(self):
        """Each pattern should appear in both train and eval when enough examples."""
        patterns = ["service_state_debug", "dbus_lookup_debug", "sensor_debug"]
        examples = []
        for p in patterns:
            for i in range(20):
                examples.append(make_example(f"Q{i}", pattern=p))

        train, eval_ = split_dataset(examples, train_ratio=0.8, seed=42)

        train_patterns = {e["metadata"]["pattern"] for e in train}
        eval_patterns = {e["metadata"]["pattern"] for e in eval_}

        # Both sets should have representation from all patterns
        assert len(train_patterns) == 3
        assert len(eval_patterns) == 3

    def test_small_dataset(self):
        examples = [make_example(f"Q{i}") for i in range(5)]
        train, eval_ = split_dataset(examples, train_ratio=0.8, seed=42)
        assert len(train) + len(eval_) == 5


class TestWriteReadJsonl:
    def test_write_and_read_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jsonl"
            examples = [make_example(f"Q{i}") for i in range(10)]
            write_jsonl(examples, path)
            assert path.exists()

            loaded = read_jsonl(path)
            assert len(loaded) == 10
            assert all("instruction" in ex for ex in loaded)
            assert all("input" in ex for ex in loaded)
            assert all("output" in ex for ex in loaded)

    def test_write_jsonl_no_metadata(self):
        """write_jsonl should strip metadata for Axolotl format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "train.jsonl"
            examples = [make_example()]
            write_jsonl(examples, path)

            loaded = read_jsonl(path)
            assert "metadata" not in loaded[0]

    def test_write_jsonl_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta.jsonl"
            examples = [make_example()]
            write_jsonl_with_metadata(examples, path)

            loaded = read_jsonl(path)
            assert "metadata" in loaded[0]

    def test_read_nonexistent_file(self):
        result = read_jsonl(Path("/nonexistent/path/file.jsonl"))
        assert result == []

    def test_handles_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "malformed.jsonl"
            with path.open("w") as fh:
                fh.write('{"instruction": "good"}\n')
                fh.write('not valid json\n')
                fh.write('{"instruction": "also good"}\n')

            loaded = read_jsonl(path)
            assert len(loaded) == 2


class TestGenerateReport:
    def test_report_structure(self):
        train = [make_example(f"Train Q{i}") for i in range(80)]
        eval_ = [make_example(f"Eval Q{i}") for i in range(20)]
        rejected = [
            {**make_example(f"Rejected Q{i}"), "rejection_reasons": ["output_too_short"]}
            for i in range(5)
        ]

        report = generate_report(train, eval_, rejected)

        assert "total_valid" in report
        assert report["total_valid"] == 100
        assert report["total_train"] == 80
        assert report["total_eval"] == 20
        assert report["total_rejected"] == 5
        assert "by_pattern" in report
        assert "by_subsystem" in report
        assert "by_source_type" in report
        assert "avg_instruction_words" in report
        assert "avg_output_words" in report
        assert "rejection_reasons" in report

    def test_empty_report(self):
        report = generate_report([], [], [])
        assert report["total_valid"] == 0
        assert report["total_train"] == 0

    def test_rejection_reasons_aggregated(self):
        rejected = [
            {**make_example(), "rejection_reasons": ["output_too_short", "missing_confidence"]},
            {**make_example(), "rejection_reasons": ["output_too_short"]},
        ]
        report = generate_report([], [], rejected)
        assert report["rejection_reasons"]["output_too_short"] == 2
        assert report["rejection_reasons"]["missing_confidence"] == 1
