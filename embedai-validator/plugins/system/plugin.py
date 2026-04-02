"""System plugin – host environment inventory and sanity checks."""

from __future__ import annotations

import platform
import socket
import time

from board.inventory import collect_environment
from core.context import ValidationContext
from core.result_model import Evidence, Status, TestResult
from plugins.base import BasePlugin, register
from utils.shell import run, tool_available


@register
class SystemPlugin(BasePlugin):
    name = "system"
    test_type = "environment"
    description = "Collects host environment info and validates basic tool availability."
    suites = ["smoke", "full"]

    def supports(self, context: ValidationContext) -> bool:
        return True  # always applicable

    def run(self, context: ValidationContext) -> list[TestResult]:
        results: list[TestResult] = []
        results.append(self._test_uname(context))
        results.append(self._test_network_interfaces(context))
        results.append(self._test_tool_inventory(context))
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _test_uname(self, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        uname = platform.uname()
        hostname = socket.gethostname()
        data = (
            f"system={uname.system} node={hostname} "
            f"release={uname.release} machine={uname.machine}"
        )
        return TestResult(
            test_id="system.uname",
            plugin_name=self.name,
            status=Status.PASS,
            duration_ms=(time.monotonic() - t0) * 1000,
            message=f"Kernel {uname.release} on {uname.machine}",
            evidence=[Evidence(source="platform.uname", data=data)],
        )

    def _test_network_interfaces(self, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        if tool_available("ip"):
            res = run(["ip", "-o", "link", "show"])
            if res.ok:
                return TestResult(
                    test_id="system.network_interfaces",
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message="Network interface list collected",
                    evidence=[Evidence(source="ip link show", data=res.stdout)],
                )
            return TestResult(
                test_id="system.network_interfaces",
                plugin_name=self.name,
                status=Status.ERROR,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"ip link show failed: {res.stderr}",
            )
        # Fallback: read /proc/net/dev
        try:
            raw = open("/proc/net/dev").read()
            return TestResult(
                test_id="system.network_interfaces",
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message="Network interfaces read from /proc/net/dev",
                evidence=[Evidence(source="/proc/net/dev", data=raw[:800])],
            )
        except OSError:
            return TestResult(
                test_id="system.network_interfaces",
                plugin_name=self.name,
                status=Status.SKIP,
                duration_ms=(time.monotonic() - t0) * 1000,
                message="'ip' not available and /proc/net/dev unreadable",
            )

    def _test_tool_inventory(self, context: ValidationContext) -> TestResult:
        t0 = time.monotonic()
        tools = {
            "i2cdetect": tool_available("i2cdetect"),
            "gpioget": tool_available("gpioget"),
            "gpioset": tool_available("gpioset"),
            "ethtool": tool_available("ethtool"),
            "ping": tool_available("ping"),
            "ip": tool_available("ip"),
            "python3": tool_available("python3"),
        }
        summary = "  ".join(f"{t}={'YES' if v else 'no'}" for t, v in tools.items())
        return TestResult(
            test_id="system.tool_inventory",
            plugin_name=self.name,
            status=Status.PASS,
            duration_ms=(time.monotonic() - t0) * 1000,
            message="Tool availability snapshot",
            evidence=[Evidence(source="shutil.which", data=summary)],
            metadata=tools,
        )
