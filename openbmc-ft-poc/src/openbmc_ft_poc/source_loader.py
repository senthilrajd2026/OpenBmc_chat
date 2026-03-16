"""
Source loader for openbmc-ft-poc.

Provides a generic interface to load content from different source adapters.
Current adapters: github_repo, github_issues.
Future adapters: company_repo, confluence, jira, etc. can be added here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .config import Config
from .logging_utils import get_logger

logger = get_logger(__name__)


def clone_or_update_repo(
    url: str,
    local_path: Path,
    branch: str = "master",
) -> dict[str, str]:
    """
    Clone a git repo if it doesn't exist, or pull latest if it does.

    Idempotent: safe to call multiple times.

    Returns:
        Dict with url, local_path, branch, commit_sha
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if (local_path / ".git").exists():
        logger.info(f"Repo exists at {local_path}; fetching latest {branch}")
        try:
            subprocess.run(
                ["git", "-C", str(local_path), "fetch", "origin", branch],
                check=True, capture_output=True, text=True, timeout=120,
            )
            subprocess.run(
                ["git", "-C", str(local_path), "checkout", branch],
                check=True, capture_output=True, text=True, timeout=30,
            )
            subprocess.run(
                ["git", "-C", str(local_path), "pull", "origin", branch],
                check=True, capture_output=True, text=True, timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning(f"git pull failed for {local_path}: {exc.stderr}")
    else:
        logger.info(f"Cloning {url} → {local_path}")
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", "--branch", branch, url, str(local_path)],
                check=True, capture_output=True, text=True, timeout=300,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(f"git clone failed for {url}: {exc.stderr}")
            return {"url": url, "local_path": str(local_path), "branch": branch, "commit_sha": ""}

    # Get current commit SHA
    sha = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(local_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        sha = result.stdout.strip()
    except Exception:
        pass

    return {
        "url": url,
        "local_path": str(local_path),
        "branch": branch,
        "commit_sha": sha,
    }


def save_manifest(manifest: list[dict[str, str]], path: Path) -> None:
    """Save a repo manifest JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    logger.info(f"Saved manifest with {len(manifest)} repos to {path}")


def load_manifest(path: Path) -> list[dict[str, str]]:
    """Load a repo manifest JSON file."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def find_doc_files(
    repo_path: Path,
    extensions: list[str] | None = None,
    subdirs: list[str] | None = None,
) -> list[Path]:
    """
    Find documentation files in a repo.

    Args:
        repo_path: Root of the cloned repo
        extensions: List of file extensions to include (default: .md, .rst, .txt)
        subdirs: List of subdirectories to search (default: entire repo)

    Returns:
        Sorted list of matching file paths
    """
    if extensions is None:
        extensions = [".md", ".rst", ".txt"]
    ext_set = set(extensions)

    if subdirs:
        search_roots = []
        for subdir in subdirs:
            p = repo_path / subdir if subdir != "." else repo_path
            if p.exists():
                search_roots.append(p)
    else:
        search_roots = [repo_path]

    found: list[Path] = []
    for root in search_roots:
        for ext in ext_set:
            found.extend(root.rglob(f"*{ext}"))

    # Deduplicate and sort
    found = sorted(set(found))
    logger.debug(f"Found {len(found)} doc files in {repo_path.name}")
    return found


def clone_all_repos(config: Config) -> list[dict[str, str]]:
    """
    Clone or update all enabled repos from config.

    Returns manifest list.
    """
    manifest: list[dict[str, str]] = []

    for repo_cfg in config.repos:
        local_path = config.project_root / repo_cfg["local_path"]
        entry = clone_or_update_repo(
            url=repo_cfg["url"],
            local_path=local_path,
            branch=repo_cfg.get("branch", "master"),
        )
        entry["id"] = repo_cfg["id"]
        manifest.append(entry)

    manifest_path = config.data_raw / "repos" / "manifest.json"
    save_manifest(manifest, manifest_path)
    return manifest
