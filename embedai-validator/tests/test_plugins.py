"""Tests for individual plugin behaviour in mocked mode."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from board.loader import load_board
from board.schemas import (
    BoardProfile, BoardMeta, Interfaces,
    I2CBus, I2CDevice, GPIOLine, UARTPort, EthernetInterface,
)
from core.context import ValidationContext
from core.result_model import Status


def _mock_context(profile: BoardProfile) -> ValidationContext:
    return ValidationContext(profile=profile, run_id="test", mock_mode=True)


def _real_context(profile: BoardProfile) -> ValidationContext:
    return ValidationContext(profile=profile, run_id="test", mock_mode=False)


def _profile_with_i2c() -> BoardProfile:
    return BoardProfile(
        board=BoardMeta(name="I2C Board"),
        interfaces=Interfaces(
            i2c=[
                I2CBus(bus=1, devices=[I2CDevice(name="eeprom", address=0x50)])
            ]
        ),
    )


def _profile_with_gpio() -> BoardProfile:
    return BoardProfile(
        board=BoardMeta(name="GPIO Board"),
        interfaces=Interfaces(
            gpio=[GPIOLine(line=23, name="reset", direction="out")]
        ),
    )


def _profile_with_uart() -> BoardProfile:
    return BoardProfile(
        board=BoardMeta(name="UART Board"),
        interfaces=Interfaces(
            uart=[UARTPort(port="/dev/ttyUSB0", baudrate=115200, loopback_required=False)]
        ),
    )


def _profile_with_eth() -> BoardProfile:
    return BoardProfile(
        board=BoardMeta(name="Eth Board"),
        interfaces=Interfaces(
            ethernet=[EthernetInterface(name="eth0", phy_expected=True)]
        ),
    )


# ---------------------------------------------------------------------------
# I2C plugin
# ---------------------------------------------------------------------------

def test_i2c_mock_all_pass() -> None:
    from plugins.i2c.plugin import I2CPlugin

    ctx = _mock_context(_profile_with_i2c())
    plugin = I2CPlugin()
    results = plugin.run(ctx)

    assert all(r.status == Status.PASS for r in results), results


def test_i2c_supports_false_when_no_i2c() -> None:
    from plugins.i2c.plugin import I2CPlugin

    profile = BoardProfile(board=BoardMeta(name="Empty Board"))
    assert not I2CPlugin().supports(_mock_context(profile))


def test_i2c_real_no_bus_fails(monkeypatch) -> None:
    """Without mock mode and without real /dev/i2c-1, expect FAIL for bus."""
    from plugins.i2c.plugin import I2CPlugin
    import plugins.i2c.plugin as i2c_mod

    # Ensure sysfs check returns False and no i2cdetect
    monkeypatch.setattr(i2c_mod, "tool_available", lambda _: False)
    monkeypatch.setattr("os.path.exists", lambda p: False)

    ctx = _real_context(_profile_with_i2c())
    plugin = I2CPlugin()
    results = plugin.run(ctx)

    bus_result = next(r for r in results if "bus_" in r.test_id)
    assert bus_result.status == Status.FAIL
    assert bus_result.error_code == "I2C_BUS_MISSING"


# ---------------------------------------------------------------------------
# GPIO plugin
# ---------------------------------------------------------------------------

def test_gpio_mock_all_pass() -> None:
    from plugins.gpio.plugin import GPIOPlugin

    ctx = _mock_context(_profile_with_gpio())
    results = GPIOPlugin().run(ctx)
    assert all(r.status == Status.PASS for r in results)


def test_gpio_no_tools_skips() -> None:
    from plugins.gpio.plugin import GPIOPlugin
    import plugins.gpio.plugin as gpio_mod

    monkeypatch_ctx = _real_context(_profile_with_gpio())

    # Patch tool_available and sysfs checks away
    import unittest.mock as mock
    with mock.patch.object(gpio_mod, "tool_available", return_value=False), \
         mock.patch("os.path.exists", return_value=False):
        results = GPIOPlugin().run(monkeypatch_ctx)

    assert all(r.status == Status.SKIP for r in results)


# ---------------------------------------------------------------------------
# UART plugin
# ---------------------------------------------------------------------------

def test_uart_mock_pass() -> None:
    from plugins.uart.plugin import UARTPlugin

    ctx = _mock_context(_profile_with_uart())
    results = UARTPlugin().run(ctx)
    assert all(r.status == Status.PASS for r in results)


def test_uart_missing_port_fails() -> None:
    from plugins.uart.plugin import UARTPlugin
    import unittest.mock as mock
    import os

    ctx = _real_context(_profile_with_uart())
    with mock.patch("os.path.exists", return_value=False):
        results = UARTPlugin().run(ctx)

    assert results[0].status == Status.FAIL
    assert results[0].error_code == "UART_PORT_MISSING"


# ---------------------------------------------------------------------------
# Ethernet plugin
# ---------------------------------------------------------------------------

def test_ethernet_mock_pass() -> None:
    from plugins.ethernet.plugin import EthernetPlugin

    ctx = _mock_context(_profile_with_eth())
    results = EthernetPlugin().run(ctx)
    assert all(r.status == Status.PASS for r in results)


def test_ethernet_missing_iface_fails() -> None:
    from plugins.ethernet.plugin import EthernetPlugin
    import unittest.mock as mock

    ctx = _real_context(_profile_with_eth())
    with mock.patch("os.path.exists", return_value=False):
        results = EthernetPlugin().run(ctx)

    presence = next(r for r in results if "presence" in r.test_id)
    assert presence.status == Status.FAIL
    assert presence.error_code == "ETH_IFACE_MISSING"


# ---------------------------------------------------------------------------
# System plugin
# ---------------------------------------------------------------------------

def test_system_always_supports() -> None:
    from plugins.system.plugin import SystemPlugin
    profile = BoardProfile(board=BoardMeta(name="Any Board"))
    assert SystemPlugin().supports(_mock_context(profile))


def test_system_returns_results() -> None:
    from plugins.system.plugin import SystemPlugin
    profile = BoardProfile(board=BoardMeta(name="Any Board"))
    ctx = _mock_context(profile)
    results = SystemPlugin().run(ctx)
    assert len(results) >= 1
    assert all(r.plugin_name == "system" for r in results)
