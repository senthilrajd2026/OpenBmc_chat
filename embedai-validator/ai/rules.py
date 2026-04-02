"""Rules-based diagnostics engine.

Each rule is a plain function that inspects a TestResult and returns a list
of suggestion strings.  Rules are registered via the @rule decorator and run
automatically in apply_rules().

Adding a new rule: write a function, decorate it with @rule, done.
"""

from __future__ import annotations

from collections.abc import Callable

from core.result_model import Status, TestResult
from utils.logger import get_logger

log = get_logger(__name__)

RuleFn = Callable[[TestResult], list[str]]
_RULES: list[RuleFn] = []


def rule(fn: RuleFn) -> RuleFn:
    """Decorator that registers a diagnostic rule function."""
    _RULES.append(fn)
    return fn


# ---------------------------------------------------------------------------
# I2C rules
# ---------------------------------------------------------------------------

@rule
def i2c_bus_missing(result: TestResult) -> list[str]:
    if result.error_code == "I2C_BUS_MISSING":
        return [
            "Verify the I2C controller is enabled in device-tree / kernel config.",
            "Check 'dmesg | grep i2c' for driver binding errors.",
            "Confirm the I2C bus number matches the hardware schematic.",
        ]
    return []


@rule
def i2c_device_missing(result: TestResult) -> list[str]:
    if result.error_code == "I2C_DEVICE_MISSING":
        return [
            "Verify device I2C address matches the YAML profile (check resistor-set or OTP).",
            "Check pull-up resistors on SDA/SCL lines (typically 4.7 kΩ).",
            "Confirm VCC/power sequencing to the device is correct.",
            "Inspect reset or enable GPIO state before I2C scan.",
        ]
    return []


@rule
def i2c_detect_error(result: TestResult) -> list[str]:
    if result.error_code == "I2C_DETECT_ERROR":
        return [
            "Ensure you have read access to /dev/i2c-N (add user to 'i2c' group).",
            "Try: sudo i2cdetect -y <bus> to test permission.",
        ]
    return []


# ---------------------------------------------------------------------------
# GPIO rules
# ---------------------------------------------------------------------------

@rule
def gpio_read_fail(result: TestResult) -> list[str]:
    if result.error_code == "GPIO_READ_FAIL":
        return [
            "Verify gpiochip device name matches the SoC (try 'gpiodetect' to list chips).",
            "Check that the GPIO line number is correct in the board profile.",
            "Ensure the user has permission to access GPIO (group 'gpio' or root).",
        ]
    return []


@rule
def gpio_skipped(result: TestResult) -> list[str]:
    if result.plugin_name == "gpio" and result.status == Status.SKIP:
        return [
            "Install libgpiod tools (apt install gpiod) to enable GPIO validation.",
            "Alternatively, export the GPIO via sysfs before running the validator.",
            "Configure the platform-specific GPIO backend if using a custom driver.",
        ]
    return []


# ---------------------------------------------------------------------------
# UART rules
# ---------------------------------------------------------------------------

@rule
def uart_port_missing(result: TestResult) -> list[str]:
    if result.error_code == "UART_PORT_MISSING":
        return [
            "Verify the UART device node path (check 'ls /dev/tty*').",
            "Confirm the kernel UART/USB-serial driver is loaded ('dmesg | grep tty').",
            "For USB-UART adapters, check USB enumeration ('lsusb').",
        ]
    return []


@rule
def uart_loopback_fail(result: TestResult) -> list[str]:
    if result.error_code in ("UART_LOOPBACK_FAIL", "UART_LOOPBACK_ERROR"):
        return [
            "Confirm a hardware loopback jumper is installed (TX→RX).",
            "Verify baud rate, parity, and stop-bit settings match both ends.",
            "Check for flow-control (RTS/CTS) issues if using hardware flow control.",
        ]
    return []


# ---------------------------------------------------------------------------
# Ethernet rules
# ---------------------------------------------------------------------------

@rule
def eth_iface_missing(result: TestResult) -> list[str]:
    if result.error_code == "ETH_IFACE_MISSING":
        return [
            "Run 'ip link' to see all available network interfaces.",
            "Verify the Ethernet MAC / PHY driver is loaded ('dmesg | grep eth').",
            "Check device-tree binding for the MAC node.",
        ]
    return []


@rule
def eth_link_down(result: TestResult) -> list[str]:
    if result.error_code == "ETH_LINK_DOWN":
        return [
            "Verify the Ethernet cable is connected and the peer port is active.",
            "Bring the interface up: 'ip link set <iface> up'.",
            "Check PHY negotiation: 'ethtool <iface>' for speed/duplex.",
            "Inspect 'dmesg' for PHY driver errors or MDIO bus issues.",
        ]
    return []


# ---------------------------------------------------------------------------
# Apply all rules
# ---------------------------------------------------------------------------

def apply_rules(results: list[TestResult]) -> list[TestResult]:
    """Run every registered rule against every result; append suggestions in-place."""
    for result in results:
        if result.status in (Status.FAIL, Status.ERROR, Status.SKIP):
            suggestions: list[str] = []
            for rule_fn in _RULES:
                suggestions.extend(rule_fn(result))
            if suggestions:
                result.suggestions = suggestions
                log.debug(
                    "Rules engine added %d suggestion(s) for %s",
                    len(suggestions),
                    result.test_id,
                )
    return results
