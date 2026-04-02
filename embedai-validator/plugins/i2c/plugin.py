"""I2C plugin – bus presence and device detection."""

from __future__ import annotations

import os
import time

from board.mapper import get_i2c_buses
from board.schemas import I2CBus, I2CDevice
from core.context import ValidationContext
from core.result_model import Evidence, Status, TestResult
from plugins.base import BasePlugin, register
from utils.shell import run, tool_available


@register
class I2CPlugin(BasePlugin):
    name = "i2c"
    test_type = "peripheral"
    description = "Validates I2C bus presence and device address detection."
    suites = ["smoke", "full"]

    def supports(self, context: ValidationContext) -> bool:
        return bool(context.profile.interfaces.i2c)

    def run(self, context: ValidationContext) -> list[TestResult]:
        results: list[TestResult] = []
        for bus in get_i2c_buses(context.profile):
            results.append(self._test_bus(bus, context))
            for device in bus.devices:
                results.append(self._test_device(bus, device, context))
        return results

    # ------------------------------------------------------------------

    def _bus_exists_sysfs(self, bus_num: int) -> bool:
        return os.path.exists(f"/dev/i2c-{bus_num}") or os.path.exists(
            f"/sys/bus/i2c/devices/i2c-{bus_num}"
        )

    def _test_bus(self, bus: I2CBus, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        test_id = f"i2c.bus_{bus.bus}"

        if context.mock_mode:
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"[MOCK] I2C bus {bus.bus} assumed present",
                evidence=[Evidence(source="mock", data=f"bus={bus.bus}")],
            )

        if self._bus_exists_sysfs(bus.bus):
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"I2C bus {bus.bus} device node present",
                evidence=[Evidence(source="sysfs", data=f"/dev/i2c-{bus.bus}")],
            )

        return TestResult(
            test_id=test_id,
            plugin_name=self.name,
            status=Status.FAIL,
            duration_ms=(time.monotonic() - t0) * 1000,
            message=f"I2C bus {bus.bus} device node not found",
            error_code="I2C_BUS_MISSING",
        )

    def _test_device(
        self, bus: I2CBus, device: I2CDevice, context: ValidationContext
    ) -> TestResult:
        t0 = time.monotonic()
        test_id = f"i2c.bus{bus.bus}.{device.name}@0x{device.address:02x}"

        if context.mock_mode:
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"[MOCK] {device.name} detected at 0x{device.address:02x}",
                evidence=[Evidence(source="mock", data=f"addr=0x{device.address:02x}")],
            )

        if tool_available("i2cdetect"):
            res = run(
                ["i2cdetect", "-y", str(bus.bus)],
                timeout=5,
            )
            if res.ok:
                hex_addr = f"{device.address:02x}"
                detected = hex_addr in res.stdout
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.PASS if detected else Status.FAIL,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=(
                        f"{device.name} detected at 0x{device.address:02x}"
                        if detected
                        else f"{device.name} NOT found at 0x{device.address:02x}"
                    ),
                    evidence=[Evidence(source="i2cdetect", data=res.stdout)],
                    error_code=None if detected else "I2C_DEVICE_MISSING",
                )
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.ERROR,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"i2cdetect failed: {res.stderr}",
                error_code="I2C_DETECT_ERROR",
            )

        # No i2cdetect and not in mock mode – fall through to SKIP
        return TestResult(
            test_id=test_id,
            plugin_name=self.name,
            status=Status.SKIP,
            duration_ms=(time.monotonic() - t0) * 1000,
            message="i2cdetect not available; cannot verify device presence",
        )
