"""Tests for the board YAML loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from board.loader import BoardLoadError, load_board
from board.schemas import BoardProfile


SAMPLE_YAML = textwrap.dedent("""\
    board:
      name: Test Board
      vendor: TestVendor
      soc: TestSoC
      os: linux
      revision: B2

    interfaces:
      i2c:
        - bus: 1
          devices:
            - name: eeprom
              address: "0x50"
            - name: temp_sensor
              address: 0x48
      gpio:
        - line: 17
          name: led
          direction: out
      uart:
        - port: /dev/ttyS0
          baudrate: 9600
          loopback_required: false
      ethernet:
        - name: eth0
          phy_expected: true
""")


@pytest.fixture()
def board_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "board.yaml"
    p.write_text(SAMPLE_YAML)
    return p


def test_load_board_happy_path(board_yaml: Path) -> None:
    profile = load_board(board_yaml)
    assert isinstance(profile, BoardProfile)
    assert profile.board.name == "Test Board"
    assert profile.board.revision == "B2"


def test_i2c_address_normalisation(board_yaml: Path) -> None:
    profile = load_board(board_yaml)
    devices = profile.interfaces.i2c[0].devices
    # both "0x50" string and 0x48 int should become integers
    assert devices[0].address == 0x50
    assert devices[1].address == 0x48


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(BoardLoadError, match="not found"):
        load_board(tmp_path / "nonexistent.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("board: [invalid: yaml: {\n")
    with pytest.raises(BoardLoadError):
        load_board(bad)


def test_missing_board_key_raises(tmp_path: Path) -> None:
    no_board = tmp_path / "no_board.yaml"
    no_board.write_text("interfaces: {}")
    with pytest.raises(BoardLoadError):
        load_board(no_board)


def test_empty_interfaces_defaults(tmp_path: Path) -> None:
    minimal = tmp_path / "minimal.yaml"
    minimal.write_text("board:\n  name: Minimal\n")
    profile = load_board(minimal)
    assert profile.interfaces.i2c == []
    assert profile.interfaces.gpio == []
    assert profile.interfaces.uart == []
    assert profile.interfaces.ethernet == []
