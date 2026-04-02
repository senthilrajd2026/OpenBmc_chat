"""Ethernet plugin – interface presence, link state, and optional connectivity."""

from __future__ import annotations

import os
import time

from board.mapper import get_ethernet_interfaces
from board.schemas import EthernetInterface
from core.context import ValidationContext
from core.result_model import Evidence, Status, TestResult
from plugins.base import BasePlugin, register
from utils.shell import run, tool_available


@register
class EthernetPlugin(BasePlugin):
    name = "ethernet"
    test_type = "peripheral"
    description = "Validates Ethernet interface presence and link status."
    suites = ["smoke", "full"]

    def supports(self, context: ValidationContext) -> bool:
        return bool(context.profile.interfaces.ethernet)

    def run(self, context: ValidationContext) -> list[TestResult]:
        results: list[TestResult] = []
        for iface in get_ethernet_interfaces(context.profile):
            results.extend(self._test_interface(iface, context))
        return results

    # ------------------------------------------------------------------

    def _sysfs_iface_exists(self, name: str) -> bool:
        return os.path.exists(f"/sys/class/net/{name}")

    def _sysfs_link_state(self, name: str) -> str | None:
        carrier_path = f"/sys/class/net/{name}/carrier"
        try:
            return open(carrier_path).read().strip()
        except OSError:
            return None

    def _test_interface(
        self, iface: EthernetInterface, context: ValidationContext
    ) -> list[TestResult]:
        t0 = time.monotonic()
        results: list[TestResult] = []

        presence_id = f"ethernet.{iface.name}.presence"
        link_id = f"ethernet.{iface.name}.link"

        if context.mock_mode:
            results.append(
                TestResult(
                    test_id=presence_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"[MOCK] {iface.name} interface assumed present",
                    evidence=[Evidence(source="mock", data=iface.name)],
                )
            )
            results.append(
                TestResult(
                    test_id=link_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"[MOCK] {iface.name} link assumed UP",
                    evidence=[Evidence(source="mock", data="carrier=1")],
                )
            )
            return results

        # Real path
        if not self._sysfs_iface_exists(iface.name):
            results.append(
                TestResult(
                    test_id=presence_id,
                    plugin_name=self.name,
                    status=Status.FAIL,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    message=f"Interface {iface.name} not found in /sys/class/net/",
                    error_code="ETH_IFACE_MISSING",
                )
            )
            return results

        results.append(
            TestResult(
                test_id=presence_id,
                plugin_name=self.name,
                status=Status.PASS,
                duration_ms=(time.monotonic() - t0) * 1000,
                message=f"Interface {iface.name} present",
                evidence=[Evidence(source="sysfs", data=f"/sys/class/net/{iface.name}")],
            )
        )

        # Link state
        t1 = time.monotonic()
        carrier = self._sysfs_link_state(iface.name)
        if carrier is None:
            results.append(
                TestResult(
                    test_id=link_id,
                    plugin_name=self.name,
                    status=Status.SKIP,
                    duration_ms=(time.monotonic() - t1) * 1000,
                    message=f"Cannot read carrier state for {iface.name}",
                )
            )
        elif carrier == "1":
            results.append(
                TestResult(
                    test_id=link_id,
                    plugin_name=self.name,
                    status=Status.PASS,
                    duration_ms=(time.monotonic() - t1) * 1000,
                    message=f"{iface.name} link is UP",
                    evidence=[Evidence(source="sysfs/carrier", data=carrier)],
                )
            )
        else:
            results.append(
                TestResult(
                    test_id=link_id,
                    plugin_name=self.name,
                    status=Status.FAIL,
                    duration_ms=(time.monotonic() - t1) * 1000,
                    message=f"{iface.name} link is DOWN (carrier={carrier})",
                    evidence=[Evidence(source="sysfs/carrier", data=carrier)],
                    error_code="ETH_LINK_DOWN",
                )
            )

        # ethtool additional info (best-effort)
        if tool_available("ethtool"):
            et = run(["ethtool", iface.name], timeout=5)
            if et.ok:
                for r in results:
                    if r.test_id == link_id:
                        r.evidence.append(Evidence(source="ethtool", data=et.stdout[:600]))

        return results
