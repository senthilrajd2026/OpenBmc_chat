"""Safe subprocess helpers for EmbedAI Validator.

All shell calls go through here so we can intercept, log, and mock them
in tests without patching subprocess directly everywhere.
"""

import shutil
import subprocess
from dataclasses import dataclass

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    cmd: list[str],
    timeout: int = 10,
    capture_stderr: bool = True,
) -> ShellResult:
    """Run *cmd* and return a ShellResult.  Never raises on non-zero exit."""
    log.debug("shell: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ShellResult(
            returncode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip() if capture_stderr else "",
        )
    except FileNotFoundError:
        log.debug("command not found: %s", cmd[0])
        return ShellResult(returncode=127, stdout="", stderr=f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        log.warning("command timed out: %s", " ".join(cmd))
        return ShellResult(returncode=124, stdout="", stderr="timeout")
    except Exception as exc:  # noqa: BLE001
        log.warning("unexpected error running %s: %s", cmd[0], exc)
        return ShellResult(returncode=1, stdout="", stderr=str(exc))


def tool_available(name: str) -> bool:
    """Return True if *name* is found on PATH."""
    return shutil.which(name) is not None
