"""
Optional OpenBMC build support for openbmc-ft-poc.

Provides:
- Build precheck (system resources, tools)
- Dry-run mode
- Minimal documented build path
- Log capture and blocker summary

This is a secondary, optional component. The dataset pipeline
continues even if the build step is skipped or fails.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .env_detect import EnvReport
from .logging_utils import get_logger

logger = get_logger(__name__)

# Minimum requirements for OpenBMC build
BUILD_MIN_RAM_GB = 8.0
BUILD_MIN_DISK_GB = 50.0
BUILD_MIN_CORES = 4

REQUIRED_TOOLS = ["git", "python3", "make", "gcc", "g++", "cpp", "patch", "diff", "bzip2", "xz"]
RECOMMENDED_TOOLS = ["curl", "wget", "diffstat", "chrpath", "socat", "cpio", "gawk"]


def run_build_precheck(
    env_report: EnvReport,
    repo_path: Path,
) -> dict[str, Any]:
    """
    Check whether the system is likely ready for an OpenBMC build.

    Args:
        env_report: Already-computed environment report
        repo_path: Path to the cloned openbmc/openbmc repo

    Returns:
        Dict with passed/blockers/warnings keys
    """
    blockers: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []

    # Platform check
    if not (env_report.is_wsl2 or env_report.is_native_linux):
        blockers.append("OpenBMC builds only supported on Linux or WSL2")
    else:
        passed.append("Linux/WSL2 environment detected")

    # RAM check
    if env_report.ram_gb < BUILD_MIN_RAM_GB:
        blockers.append(
            f"Insufficient RAM: {env_report.ram_gb}GB (need {BUILD_MIN_RAM_GB}GB+)"
        )
    else:
        passed.append(f"RAM: {env_report.ram_gb}GB ✓")

    # Disk check
    if env_report.disk_free_gb < BUILD_MIN_DISK_GB:
        blockers.append(
            f"Insufficient disk: {env_report.disk_free_gb}GB free "
            f"(need {BUILD_MIN_DISK_GB}GB+)"
        )
    else:
        passed.append(f"Disk: {env_report.disk_free_gb}GB free ✓")

    # CPU cores
    if env_report.cpu_cores < BUILD_MIN_CORES:
        warnings.append(
            f"Only {env_report.cpu_cores} CPU cores; build will be slow "
            f"(recommend {BUILD_MIN_CORES}+)"
        )
    else:
        passed.append(f"CPU cores: {env_report.cpu_cores} ✓")

    # Required tools
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool):
            passed.append(f"Tool '{tool}' found")
        else:
            blockers.append(f"Required tool not found: {tool}")

    # Recommended tools
    for tool in RECOMMENDED_TOOLS:
        if not shutil.which(tool):
            warnings.append(f"Recommended tool missing: {tool}")

    # Repo check
    if not repo_path.exists() or not (repo_path / ".git").exists():
        blockers.append(f"OpenBMC repo not found at {repo_path}; run 'make clone' first")
    else:
        passed.append("OpenBMC repo present")

    return {
        "can_build": len(blockers) == 0,
        "passed": passed,
        "blockers": blockers,
        "warnings": warnings,
    }


def run_minimal_build(
    repo_path: Path,
    machine: str = "qemuarm",
    dry_run: bool = False,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """
    Attempt a minimal documented OpenBMC build.

    Uses qemuarm as default (fastest to build, no hardware needed).

    Args:
        repo_path: Path to cloned openbmc repo
        machine: BitBake MACHINE target
        dry_run: If True, print commands but don't execute
        log_path: Path to write build log

    Returns:
        Dict with success/blockers/summary
    """
    if not repo_path.exists():
        return {"success": False, "summary": "OpenBMC repo not found"}

    log_lines: list[str] = []

    def _run(cmd: str, cwd: Path | None = None) -> tuple[int, str, str]:
        log_lines.append(f"$ {cmd}")
        if dry_run:
            logger.info(f"[dry-run] {cmd}")
            return (0, "", "")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=str(cwd or repo_path),
                capture_output=True, text=True, timeout=3600,
            )
            log_lines.extend(result.stdout.splitlines()[-50:])
            if result.returncode != 0:
                log_lines.extend(result.stderr.splitlines()[-30:])
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "Build timed out")
        except Exception as exc:
            return (-1, "", str(exc))

    blockers: list[str] = []

    # Step 1: Source the OpenBMC env setup
    setup_script = repo_path / "setup"
    if not setup_script.exists():
        return {"success": False, "summary": "OpenBMC 'setup' script not found in repo"}

    # Step 2: Build commands (sourcing and bitbake must be in same shell)
    build_cmd = (
        f"cd {repo_path} && "
        f". setup {machine} build && "
        f"bitbake obmc-phosphor-image --dry-run 2>&1 | head -50"
        if dry_run else
        f"cd {repo_path} && "
        f". setup {machine} build && "
        f"bitbake obmc-phosphor-image"
    )

    start = time.time()
    rc, stdout, stderr = _run(build_cmd)
    elapsed = time.time() - start

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(log_lines))
        logger.info(f"Build log written to {log_path}")

    success = rc == 0
    summary = (
        f"Build {'completed (dry-run)' if dry_run else ('succeeded' if success else 'FAILED')} "
        f"in {elapsed:.0f}s for MACHINE={machine}"
    )
    if not success and stderr:
        blockers.append(stderr.strip()[:500])

    return {
        "success": success,
        "dry_run": dry_run,
        "machine": machine,
        "elapsed_s": round(elapsed, 1),
        "summary": summary,
        "blockers": blockers,
        "log_lines": len(log_lines),
    }
