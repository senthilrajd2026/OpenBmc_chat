"""Board inventory helpers – collect runtime system information."""

from __future__ import annotations

import platform
import socket

from utils.logger import get_logger
from utils.shell import run, tool_available

log = get_logger(__name__)


def collect_environment() -> dict[str, str]:
    """Return a dict of key environment facts about the current host."""
    info: dict[str, str] = {}

    info["hostname"] = socket.gethostname()
    info["python_version"] = platform.python_version()
    info["platform"] = platform.platform()
    info["machine"] = platform.machine()
    info["processor"] = platform.processor() or "unknown"

    # uname
    uname = platform.uname()
    info["kernel"] = uname.release
    info["os_name"] = uname.system

    # Network interfaces via ip/ifconfig
    if tool_available("ip"):
        result = run(["ip", "-o", "link", "show"])
        if result.ok:
            ifaces = [
                line.split(":")[1].strip()
                for line in result.stdout.splitlines()
                if ":" in line
            ]
            info["network_interfaces"] = ", ".join(ifaces)

    # Tool availability snapshot
    tools = ["i2cdetect", "gpioget", "gpioset", "ethtool", "ping", "ip", "python3"]
    info["available_tools"] = ", ".join(t for t in tools if tool_available(t))

    return info
