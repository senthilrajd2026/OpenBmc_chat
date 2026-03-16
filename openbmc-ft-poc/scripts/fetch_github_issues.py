#!/usr/bin/env python3
"""
Fetch GitHub issues from configured OpenBMC repos.

Outputs normalized issue JSONL to data/intermediate/issues/.
Rate-limit safe. Requires GITHUB_TOKEN in .env for best results.

Usage:
    python3 scripts/fetch_github_issues.py [--repo openbmc/openbmc]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.github_client import GitHubClient
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GitHub issues for openbmc-ft-poc")
    parser.add_argument("--repo", help="Override: fetch from this repo only (owner/repo)")
    parser.add_argument("--max-pages", type=int, default=None, help="Override max pages")
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    client = GitHubClient(token=cfg.github_token)

    # Check rate limit
    rate = client.check_rate_limit()
    if rate:
        remaining = rate.get("remaining", "?")
        logger.info(f"GitHub API rate limit remaining: {remaining}/hr")
        if isinstance(remaining, int) and remaining < 10:
            logger.warning("Rate limit very low! Consider waiting or setting GITHUB_TOKEN.")

    out_dir = cfg.data_intermediate / "issues"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = cfg.issue_sources
    if args.repo:
        # Filter or add the specified repo
        sources = [s for s in sources if s["repo"] == args.repo]
        if not sources:
            sources = [{
                "id": "cli-override",
                "repo": args.repo,
                "state": "closed",
                "max_pages": args.max_pages or 3,
                "per_page": 30,
                "skip_prs": True,
                "min_body_length": 50,
                "labels": [],
            }]

    total_fetched = 0

    for source in sources:
        repo = source["repo"]
        max_pages = args.max_pages or source.get("max_pages", 3)

        logger.info(f"Fetching issues from {repo} (max {max_pages} pages)...")
        issues = client.fetch_issues(
            repo=repo,
            state=source.get("state", "closed"),
            labels=source.get("labels", []),
            max_pages=max_pages,
            per_page=source.get("per_page", 30),
            skip_prs=source.get("skip_prs", True),
            min_body_length=source.get("min_body_length", 50),
        )

        # Save to JSONL
        safe_name = repo.replace("/", "_")
        out_path = out_dir / f"issues_{safe_name}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for issue in issues:
                fh.write(json.dumps(issue, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(issues)} issues to {out_path}")
        total_fetched += len(issues)

    print(f"\nTotal issues fetched: {total_fetched}")
    print(f"Output directory: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
