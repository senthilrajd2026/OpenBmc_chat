"""UART plugin – port presence and optional loopback validation."""

from __future__ import annotations

import os
import time

from board.mapper import get_uart_ports
from board.schemas import UARTPort
from core.context import ValidationContext
from core.result_model import Evidence, Status, TestResult
from plugins.base import BasePlugin, register
from utils.logger import get_logger
from utils.shell import tool_available

log = get_logger(__name__)


def _pyserial_available() -> bool:
    try:
        import serial  # noqa: F401
        return True
    except ImportError:
        return False


@register
class UARTPlugin(BasePlugin):
    name = "uart"
    test_type = "peripheral"
    description = "Validates UART port existence and optional loopback integrity."
    suites = ["full"]

    def supports(self, context: ValidationContext) -> bool:
        return bool(context.profile.interfaces.uart)

    def run(self, context: ValidationContext) -> list[TestResult]:
        results: list[TestResult] = []
        for port in get_uart_ports(context.profile):
            results.append(self._test_port(port, context))
        return results

    # ------------------------------------------------------------------

    def _test_port(self, port: UARTPort, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        test_id = f"uart.{port.port.replace('/', '_')}"

        if context.mock_mode:
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"[MOCK] UART {port.port} assumed present at {port.baudrate} baud",
                evidence=[Evidence(source="mock", data=f"port={port.port} baud={port.baudrate}")],
            )

        # Check device node
        if not os.path.exists(port.port):
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.FAIL,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"UART device node not found: {port.port}",
                error_code="UART_PORT_MISSING",
            )

        # Port exists – attempt loopback if requested and pyserial is available
        if port.loopback_required:
            if not _pyserial_available():
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.SKIP,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=(
                        f"UART {port.port} exists but loopback required and "
                        "pyserial not installed"
                    ),
                )
            return self._loopback_test(port, t0)

        return TestResult(
            test_id=test_id,
            plugin_name=self.name,
            status=Status.PASS,
            duration_ms=(time.monotonic() - t0) * 1000,
            message=f"UART device node {port.port} present",
            evidence=[Evidence(source="os.path.exists", data=port.port)],
        )

    def _loopback_test(self, port: UARTPort, t0: float) -> TestResult:
        """Send a byte and read it back (requires a hardware loopback jumper)."""
        import serial  # type: ignore

        test_id = f"uart.{port.port.replace('/', '_')}.loopback"
        payload = b"\xAA\x55"
        try:
            with serial.Serial(port.port, baudrate=port.baudrate, timeout=1) as ser:
                ser.write(payload)
                received = ser.read(len(payload))
            if received == payload:
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"UART loopback OK on {port.port}",
                    evidence=[Evidence(source="pyserial", data=f"sent={payload.hex()} recv={received.hex()}")],
                )
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.FAIL,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"UART loopback mismatch: sent {payload.hex()} got {received.hex()}",
                error_code="UART_LOOPBACK_FAIL",
            )
        except Exception as exc:  # noqa: BLE001
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.ERROR,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"UART loopback error: {exc}",
                error_code="UART_LOOPBACK_ERROR",
            )
