#!/usr/bin/env python3
"""
Clone or update OpenBMC source repos.

Uses configs/sources.yaml for repo list.
Idempotent: safe to run multiple times.
Saves a manifest JSON with commit SHAs.

Usage:
    python3 scripts/clone_sources.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging
from openbmc_ft_poc.source_loader import clone_all_repos

setup_logging()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone OpenBMC source repos")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be cloned without doing it")
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    if args.dry_run:
        print("Repos that would be cloned:")
        for repo in cfg.repos:
            print(f"  {repo['url']} → {repo['local_path']} (branch: {repo.get('branch', 'master')})")
        return 0

    manifest = clone_all_repos(cfg)
    print(f"\nCloned/updated {len(manifest)} repos.")
    for entry in manifest:
        sha = entry.get("commit_sha", "unknown")[:12]
        print(f"  {entry.get('id', '')} @ {sha}  →  {entry.get('local_path', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
