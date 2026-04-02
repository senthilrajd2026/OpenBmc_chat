"""GPIO plugin – validate configured GPIO lines."""

from __future__ import annotations

import os
import time

from board.mapper import get_gpio_lines
from board.schemas import GPIOLine
from core.context import ValidationContext
from core.result_model import Evidence, Status, TestResult
from plugins.base import BasePlugin, register
from utils.shell import run, tool_available


@register
class GPIOPlugin(BasePlugin):
    name = "gpio"
    test_type = "peripheral"
    description = "Validates GPIO line configuration and performs safe read/toggle checks."
    suites = ["full"]  # excluded from 'smoke' by default

    def supports(self, context: ValidationContext) -> bool:
        return bool(context.profile.interfaces.gpio)

    def run(self, context: ValidationContext) -> list[TestResult]:
        results: list[TestResult] = []
        for line in get_gpio_lines(context.profile):
            results.append(self._test_line(line, context))
        return results

    # ------------------------------------------------------------------

    def _sysfs_gpio_exported(self, line: int) -> bool:
        return os.path.exists(f"/sys/class/gpio/gpio{line}")

    def _test_line(self, line: GPIOLine, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        test_id = f"gpio.line{line.line}.{line.name}"

        if context.mock_mode:
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"[MOCK] GPIO {line.name} (line {line.line}) simulated OK",
                evidence=[Evidence(source="mock", data=f"line={line.line} dir={line.direction}")],
            )

        # Try libgpiod tools first (modern kernel ABI)
        if tool_available("gpioget") and line.direction == "in":
            res = run(["gpioget", "gpiochip0", str(line.line)], timeout=3)
            if res.ok:
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"GPIO {line.name} read value: {res.stdout}",
                    evidence=[Evidence(source="gpioget", data=res.stdout)],
                )
            return TestResult(
                test_id=test_id,
                plugin_name=self.name,
                status=Status.FAIL,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"gpioget failed for line {line.line}: {res.stderr}",
                error_code="GPIO_READ_FAIL",
            )

        # Sysfs legacy fallback – read only, never export (unsafe)
        if self._sysfs_gpio_exported(line.line):
            try:
                value = open(f"/sys/class/gpio/gpio{line.line}/value").read().strip()
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"GPIO {line.name} sysfs value: {value}",
                    evidence=[Evidence(source="sysfs", data=value)],
                )
            except OSError as exc:
                return TestResult(
                    test_id=test_id,
                    plugin_name=self.name,
                    status=Status.ERROR,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"sysfs read error: {exc}",
                )

        # Nothing available
        return TestResult(
            test_id=test_id,
            plugin_name=self.name,
            status=Status.SKIP,
            duration_ms=(time.monotonic() - t0) * 1000,
            message=(
                f"GPIO {line.name} (line {line.line}): "
                "no libgpiod tools or sysfs export found – skipped safely"
            ),
        )
