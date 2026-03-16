"""
Environment detection for openbmc-ft-poc.

Detects WSL2 vs native Linux, hardware capabilities,
GPU/CUDA availability, and pipeline feasibility.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EnvReport:
    """Comprehensive environment capability report."""

    # Platform
    is_wsl2: bool = False
    is_native_linux: bool = False
    os_name: str = ""
    distro: str = ""
    distro_version: str = ""
    kernel_version: str = ""

    # Hardware
    cpu_cores: int = 0
    ram_gb: float = 0.0
    disk_free_gb: float = 0.0

    # Toolchain
    python_version: str = ""
    python_ok: bool = False
    git_version: str = ""
    git_ok: bool = False

    # GPU / CUDA
    nvidia_visible: bool = False
    cuda_visible: bool = False
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    cuda_version: str = ""

    # Pipeline feasibility
    can_generate_dataset: bool = False
    can_run_openbmc_build: bool = False
    can_fine_tune: bool = False

    # Warnings
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _run(cmd: list[str], timeout: int = 10) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _read_file(path: str) -> str:
    """Read a file safely, return empty string on error."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def detect_environment() -> EnvReport:
    """
    Perform full environment detection and return an EnvReport.

    Does not raise exceptions; all failures produce warnings.
    """
    report = EnvReport()

    # ------------------------------------------------------------------
    # Platform detection
    # ------------------------------------------------------------------
    report.os_name = platform.system()

    # WSL2 detection: check /proc/version or /proc/sys/kernel/osrelease
    proc_version = _read_file("/proc/version").lower()
    kernel_release = _run(["uname", "-r"])
    report.kernel_version = kernel_release

    if "microsoft" in proc_version or "wsl" in kernel_release.lower():
        report.is_wsl2 = True
        report.is_native_linux = False
    elif platform.system() == "Linux":
        report.is_native_linux = True

    # Distro detection
    os_release = _read_file("/etc/os-release")
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            report.distro = line.split("=", 1)[1].strip('"')
        if line.startswith("VERSION_ID="):
            report.distro_version = line.split("=", 1)[1].strip('"')

    if not report.distro:
        report.distro = platform.platform()

    # ------------------------------------------------------------------
    # Hardware
    # ------------------------------------------------------------------
    # CPU cores
    try:
        import multiprocessing
        report.cpu_cores = multiprocessing.cpu_count()
    except Exception:
        report.cpu_cores = 1

    # RAM (parse /proc/meminfo)
    meminfo = _read_file("/proc/meminfo")
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            try:
                kb = int(line.split()[1])
                report.ram_gb = round(kb / 1024 / 1024, 1)
            except Exception:
                pass
            break

    # Free disk
    try:
        stat = shutil.disk_usage(".")
        report.disk_free_gb = round(stat.free / 1024 ** 3, 1)
    except Exception:
        report.disk_free_gb = 0.0

    # ------------------------------------------------------------------
    # Toolchain
    # ------------------------------------------------------------------
    report.python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    report.python_ok = sys.version_info >= (3, 11)
    if not report.python_ok:
        report.warnings.append(
            f"Python {report.python_version} detected; 3.11+ required."
        )
        report.recommendations.append("Upgrade to Python 3.11: sudo apt install python3.11")

    git_out = _run(["git", "--version"])
    report.git_version = git_out
    report.git_ok = git_out.startswith("git version")
    if not report.git_ok:
        report.warnings.append("git not found in PATH")
        report.recommendations.append("Install git: sudo apt install git")

    # ------------------------------------------------------------------
    # GPU / CUDA detection
    # ------------------------------------------------------------------
    nvidia_smi = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if nvidia_smi:
        report.nvidia_visible = True
        parts = nvidia_smi.split(",")
        if len(parts) >= 2:
            report.gpu_name = parts[0].strip()
            mem_str = parts[1].strip()  # e.g. "8192 MiB"
            try:
                mib = float(re.search(r"[\d.]+", mem_str).group())
                report.gpu_vram_gb = round(mib / 1024, 1)
            except Exception:
                pass

    # CUDA toolkit visibility
    nvcc = _run(["nvcc", "--version"])
    if nvcc and "release" in nvcc.lower():
        report.cuda_visible = True
        m = re.search(r"release ([\d.]+)", nvcc, re.IGNORECASE)
        if m:
            report.cuda_version = m.group(1)

    # Also check CUDA via torch if available
    if not report.cuda_visible:
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                report.cuda_visible = True
                report.cuda_version = torch.version.cuda or "unknown"
                if not report.nvidia_visible:
                    report.nvidia_visible = True
                    report.gpu_name = torch.cuda.get_device_name(0)
                    vram = torch.cuda.get_device_properties(0).total_memory
                    report.gpu_vram_gb = round(vram / 1024 ** 3, 1)
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Feasibility assessment
    # ------------------------------------------------------------------
    # Dataset generation: needs Python 3.11+, git, 2+ GB RAM, 10+ GB disk
    report.can_generate_dataset = (
        report.python_ok
        and report.git_ok
        and report.ram_gb >= 2.0
        and report.disk_free_gb >= 10.0
    )

    # OpenBMC build: needs significant RAM (8GB+) and disk (50GB+), Linux
    report.can_run_openbmc_build = (
        (report.is_wsl2 or report.is_native_linux)
        and report.ram_gb >= 8.0
        and report.disk_free_gb >= 50.0
        and report.cpu_cores >= 4
    )

    # Fine-tuning: needs CUDA + enough VRAM (6GB+ for 1B QLoRA)
    report.can_fine_tune = (
        report.cuda_visible
        and report.gpu_vram_gb >= 6.0
    )

    # ------------------------------------------------------------------
    # Warnings and recommendations
    # ------------------------------------------------------------------
    if not report.nvidia_visible:
        report.warnings.append("No NVIDIA GPU detected. Fine-tuning not possible locally.")
        report.recommendations.append(
            "Install NVIDIA drivers or use a cloud GPU instance for training."
        )
    elif not report.cuda_visible:
        report.warnings.append(
            f"GPU detected ({report.gpu_name}) but CUDA not visible."
        )
        report.recommendations.append(
            "Install CUDA toolkit: https://developer.nvidia.com/cuda-downloads"
        )
    elif report.gpu_vram_gb < 6.0:
        report.warnings.append(
            f"GPU VRAM {report.gpu_vram_gb}GB may be insufficient for 1B model fine-tuning."
        )

    if not report.can_generate_dataset:
        report.warnings.append("System may not meet minimum requirements for dataset generation.")

    if report.disk_free_gb < 10.0:
        report.warnings.append(
            f"Only {report.disk_free_gb}GB free disk. Dataset pipeline needs ~10GB+."
        )
        report.recommendations.append("Free up disk space before running the pipeline.")

    if report.ram_gb < 4.0:
        report.warnings.append(
            f"Only {report.ram_gb}GB RAM detected. Some pipeline steps may be slow."
        )

    if report.is_wsl2:
        # WSL2-specific checks
        wsl_memory = _read_file("/proc/meminfo")
        report.recommendations.append(
            "WSL2 detected. Ensure .wslconfig sets adequate memory: "
            "[wsl2] memory=8GB (see README for details)."
        )

    return report


def format_report(report: EnvReport, verbose: bool = True) -> str:
    """Format an EnvReport as a human-readable string."""
    lines = [
        "=" * 60,
        "  OpenBMC FT PoC — Environment Report",
        "=" * 60,
        "",
        "Platform:",
        f"  WSL2:          {'YES' if report.is_wsl2 else 'no'}",
        f"  Native Linux:  {'YES' if report.is_native_linux else 'no'}",
        f"  OS:            {report.distro}",
        f"  Kernel:        {report.kernel_version}",
        "",
        "Hardware:",
        f"  CPU cores:     {report.cpu_cores}",
        f"  RAM:           {report.ram_gb} GB",
        f"  Free disk:     {report.disk_free_gb} GB",
        "",
        "Toolchain:",
        f"  Python:        {report.python_version} {'✓' if report.python_ok else '✗ (need 3.11+)'}",
        f"  git:           {report.git_version or 'NOT FOUND'} {'✓' if report.git_ok else '✗'}",
        "",
        "GPU / CUDA:",
        f"  NVIDIA GPU:    {'YES — ' + report.gpu_name if report.nvidia_visible else 'not detected'}",
        f"  VRAM:          {report.gpu_vram_gb} GB" if report.nvidia_visible else "  VRAM:          N/A",
        f"  CUDA:          {report.cuda_version if report.cuda_visible else 'not visible'}",
        "",
        "Pipeline Feasibility:",
        f"  Dataset gen:   {'YES' if report.can_generate_dataset else 'NO — see warnings'}",
        f"  OpenBMC build: {'YES' if report.can_run_openbmc_build else 'NO (optional step)'}",
        f"  Fine-tuning:   {'YES' if report.can_fine_tune else 'NO — GPU/CUDA needed'}",
    ]

    if report.warnings:
        lines += ["", "Warnings:"]
        for w in report.warnings:
            lines.append(f"  ⚠  {w}")

    if report.recommendations:
        lines += ["", "Recommendations:"]
        for r in report.recommendations:
            lines.append(f"  →  {r}")

    lines += ["", "=" * 60]
    return "\n".join(lines)
