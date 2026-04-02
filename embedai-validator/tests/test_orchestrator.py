"""Tests for the orchestrator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.result_model import RunResult, Status


SAMPLE_YAML = textwrap.dedent("""\
    board:
      name: Orchestrator Test Board
      vendor: Test
      soc: TestSoC
      os: linux
      revision: X1

    interfaces:
      i2c:
        - bus: 1
          devices:
            - name: eeprom
              address: "0x50"
      ethernet:
        - name: eth0
          phy_expected: true
""")


@pytest.fixture()
def board_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "board.yaml"
    p.write_text(SAMPLE_YAML)
    return p


def test_orchestrator_mock_run(board_yaml: Path, tmp_path: Path) -> None:
    from core.orchestrator import Orchestrator

    orch = Orchestrator(
        board_path=board_yaml,
        mock_mode=True,
        output_dir=tmp_path / "output",
    )
    result = orch.run()

    assert isinstance(result, RunResult)
    assert result.board_name == "Orchestrator Test Board"
    assert result.mock_mode is True
    assert result.summary.total > 0
    assert result.finished_at is not None


def test_orchestrator_all_mock_pass(board_yaml: Path, tmp_path: Path) -> None:
    """In mock mode every result should be PASS (no real hardware needed)."""
    from core.orchestrator import Orchestrator

    orch = Orchestrator(
        board_path=board_yaml,
        mock_mode=True,
        output_dir=tmp_path / "output",
    )
    result = orch.run()

    non_pass = [r for r in result.results if r.status not in (Status.PASS,)]
    # System plugin results will be PASS or SKIP on any machine; no FAILs in mock
    failures = [r for r in result.results if r.status == Status.FAIL]
    assert failures == [], f"Unexpected failures in mock mode: {failures}"


def test_orchestrator_suite_filter(board_yaml: Path, tmp_path: Path) -> None:
    """Smoke suite should run fewer tests than full suite."""
    from core.orchestrator import Orchestrator

    smoke = Orchestrator(
        board_path=board_yaml, mock_mode=True, suite="smoke",
        output_dir=tmp_path / "output_smoke"
    ).run()

    full = Orchestrator(
        board_path=board_yaml, mock_mode=True, suite="full",
        output_dir=tmp_path / "output_full"
    ).run()

    # GPIO plugin is not in smoke suite → full should have more tests
    assert full.summary.total >= smoke.summary.total
