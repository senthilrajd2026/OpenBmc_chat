"""Tests for the rules-based diagnostics engine."""

from __future__ import annotations

import pytest

from ai.rules import apply_rules
from core.result_model import Evidence, Status, TestResult


def _make_result(
    test_id: str = "x.test",
    plugin_name: str = "i2c",
    status: Status = Status.FAIL,
    error_code: str | None = None,
) -> TestResult:
    return TestResult(
        test_id=test_id,
        plugin_name=plugin_name,
        status=status,
        message="test message",
        error_code=error_code,
    )


def test_i2c_bus_missing_gets_suggestions() -> None:
    r = _make_result(error_code="I2C_BUS_MISSING")
    [r] = apply_rules([r])
    assert len(r.suggestions) > 0
    assert any("i2c" in s.lower() or "bus" in s.lower() for s in r.suggestions)


def test_i2c_device_missing_gets_suggestions() -> None:
    r = _make_result(error_code="I2C_DEVICE_MISSING")
    [r] = apply_rules([r])
    assert len(r.suggestions) > 0
    assert any("address" in s.lower() or "pull" in s.lower() for s in r.suggestions)


def test_eth_link_down_gets_suggestions() -> None:
    r = _make_result(plugin_name="ethernet", error_code="ETH_LINK_DOWN")
    [r] = apply_rules([r])
    assert len(r.suggestions) > 0
    assert any("cable" in s.lower() or "link" in s.lower() for s in r.suggestions)


def test_uart_port_missing_gets_suggestions() -> None:
    r = _make_result(plugin_name="uart", error_code="UART_PORT_MISSING")
    [r] = apply_rules([r])
    assert len(r.suggestions) > 0
    assert any("dev" in s.lower() or "uart" in s.lower() or "tty" in s.lower() for s in r.suggestions)


def test_gpio_skipped_gets_suggestions() -> None:
    r = _make_result(plugin_name="gpio", status=Status.SKIP, error_code=None)
    [r] = apply_rules([r])
    assert len(r.suggestions) > 0


def test_passing_result_no_suggestions() -> None:
    r = _make_result(status=Status.PASS)
    [r] = apply_rules([r])
    assert r.suggestions == []


def test_multiple_results_independent() -> None:
    results = [
        _make_result("a", error_code="I2C_BUS_MISSING"),
        _make_result("b", status=Status.PASS),
        _make_result("c", error_code="ETH_LINK_DOWN", plugin_name="ethernet"),
    ]
    out = apply_rules(results)
    assert len(out[0].suggestions) > 0
    assert out[1].suggestions == []
    assert len(out[2].suggestions) > 0
