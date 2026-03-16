"""
Repository mining for openbmc-ft-poc.

Extracts engineering signals from cloned OpenBMC repos:
- Service unit file names and descriptions
- D-Bus interface strings (xyz.openbmc_project.*)
- Log/error strings from source files
- Architecture and design document content
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .logging_utils import get_logger

logger = get_logger(__name__)

# D-Bus interface pattern: xyz.openbmc_project.*
_DBUS_IFACE_RE = re.compile(r"\bxyz\.openbmc_project\.[A-Za-z0-9._]+")
_DBUS_PATH_RE = re.compile(r"/xyz/openbmc_project/[A-Za-z0-9_/]+")

# systemd unit file extensions
_SERVICE_EXTENSIONS = {".service", ".socket", ".target", ".timer"}

# Log/error string patterns from C++ sources
_LOG_PATTERNS = [
    re.compile(r'log\s*<\s*level::[A-Za-z]+\s*>\s*\(\s*"([^"]{10,})"'),
    re.compile(r'phosphor::logging::log\s*<\s*[^>]+\s*>\s*\(([^)]{10,})\)'),
    re.compile(r'lg2::(error|warning|info|debug)\s*\(\s*"([^"]{10,})"'),
    re.compile(r'"(.*(?:failed|error|unable|cannot|invalid|not found)[^"]{0,60})"', re.IGNORECASE),
]


def extract_service_units(repo_path: Path) -> list[dict[str, Any]]:
    """
    Find and parse systemd service unit files in a repo.

    Returns list of service signal records.
    """
    signals: list[dict[str, Any]] = []
    repo_name = repo_path.name

    service_files = []
    for ext in _SERVICE_EXTENSIONS:
        service_files.extend(repo_path.rglob(f"*{ext}"))

    for sf in service_files:
        try:
            content = sf.read_text(encoding="utf-8", errors="replace")
            rel_path = str(sf.relative_to(repo_path))
            record = _parse_service_unit(content, rel_path, repo_name)
            if record:
                signals.append(record)
        except Exception as exc:
            logger.debug(f"Failed to parse service file {sf}: {exc}")

    logger.info(f"Extracted {len(signals)} service signals from {repo_name}")
    return signals


def _parse_service_unit(content: str, path: str, repo: str) -> dict[str, Any] | None:
    """Parse a systemd unit file into a signal record."""
    name = Path(path).name
    description = ""
    exec_start = ""
    wants = []
    after = []

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Description="):
            description = line.split("=", 1)[1].strip()
        elif line.startswith("ExecStart="):
            exec_start = line.split("=", 1)[1].strip()
        elif line.startswith("Wants="):
            wants.extend(line.split("=", 1)[1].split())
        elif line.startswith("After="):
            after.extend(line.split("=", 1)[1].split())

    if not (name or description):
        return None

    return {
        "source_type": "service_unit",
        "repo": repo,
        "path": path,
        "service_name": name,
        "description": description,
        "exec_start": exec_start,
        "wants": wants,
        "after": after,
        "raw": content[:1000],  # keep snippet for generation
    }


def extract_dbus_strings(repo_path: Path) -> list[dict[str, Any]]:
    """
    Extract D-Bus interface strings and object paths from repo files.

    Searches .cpp, .hpp, .c, .h, .py, .yaml, .json, .md files.
    """
    signals: list[dict[str, Any]] = []
    repo_name = repo_path.name
    extensions = {".cpp", ".hpp", ".c", ".h", ".py", ".yaml", ".yml", ".json", ".md"}

    seen_ifaces: set[str] = set()
    seen_paths: set[str] = set()

    source_files = [f for f in repo_path.rglob("*") if f.suffix in extensions and f.is_file()]

    for sf in source_files:
        try:
            content = sf.read_text(encoding="utf-8", errors="replace")
            rel_path = str(sf.relative_to(repo_path))

            ifaces = _DBUS_IFACE_RE.findall(content)
            paths = _DBUS_PATH_RE.findall(content)

            for iface in ifaces:
                if iface not in seen_ifaces:
                    seen_ifaces.add(iface)
                    signals.append({
                        "source_type": "dbus_interface",
                        "repo": repo_name,
                        "path": rel_path,
                        "value": iface,
                        "kind": "interface",
                    })

            for path in paths:
                if path not in seen_paths:
                    seen_paths.add(path)
                    signals.append({
                        "source_type": "dbus_path",
                        "repo": repo_name,
                        "path": rel_path,
                        "value": path,
                        "kind": "object_path",
                    })

        except Exception as exc:
            logger.debug(f"Failed to scan {sf}: {exc}")

    logger.info(
        f"Extracted {len(signals)} D-Bus strings "
        f"({len(seen_ifaces)} interfaces, {len(seen_paths)} paths) from {repo_name}"
    )
    return signals


def extract_log_strings(repo_path: Path) -> list[dict[str, Any]]:
    """
    Extract log/error strings from C++ source files.

    These are useful as "evidence" patterns for the training data.
    """
    signals: list[dict[str, Any]] = []
    repo_name = repo_path.name
    c_files = list(repo_path.rglob("*.cpp")) + list(repo_path.rglob("*.hpp"))

    for sf in c_files[:500]:  # cap to avoid scanning too many files
        try:
            content = sf.read_text(encoding="utf-8", errors="replace")
            rel_path = str(sf.relative_to(repo_path))
            found: set[str] = set()

            for pattern in _LOG_PATTERNS:
                for m in pattern.finditer(content):
                    msg = m.group(m.lastindex or 1).strip()
                    if msg and len(msg) > 10 and msg not in found:
                        found.add(msg)
                        signals.append({
                            "source_type": "log_string",
                            "repo": repo_name,
                            "path": rel_path,
                            "value": msg,
                        })
        except Exception as exc:
            logger.debug(f"Failed to extract log strings from {sf}: {exc}")

    logger.info(f"Extracted {len(signals)} log strings from {repo_name}")
    return signals


def extract_repo_metadata(repo_path: Path) -> dict[str, Any]:
    """
    Extract high-level metadata from a cloned repo.

    Returns dict with repo name, top-level README snippet,
    detected subsystem indicators, etc.
    """
    repo_name = repo_path.name
    metadata: dict[str, Any] = {
        "repo": repo_name,
        "path": str(repo_path),
        "top_services": [],
        "top_dbus_ifaces": [],
        "readme_snippet": "",
        "doc_file_count": 0,
    }

    # Top-level README
    for readme_name in ["README.md", "README.rst", "README"]:
        readme = repo_path / readme_name
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="replace")
            metadata["readme_snippet"] = text[:2000]
            break

    # Count doc files
    metadata["doc_file_count"] = len(list(repo_path.rglob("*.md")))

    return metadata
