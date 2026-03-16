"""
GitHub API client for openbmc-ft-poc.

Handles rate limiting, pagination, and safe issue/repo fetching.
Designed to work with or without a GitHub token.
"""

from __future__ import annotations

import time
from typing import Any, Generator, Optional

import requests

from .logging_utils import get_logger

logger = get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "openbmc-ft-poc/0.1",
}


class GitHubClient:
    """
    Thin GitHub REST API client.

    Supports:
    - Authentication via token (strongly recommended)
    - Automatic rate limit handling with backoff
    - Pagination over issues
    - PR filtering
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"
            logger.info("GitHub client initialized with authentication token.")
        else:
            logger.warning(
                "No GitHub token set. Rate limit is 60 req/hr (unauthenticated). "
                "Set GITHUB_TOKEN in .env to increase to 5000/hr."
            )

    def _get(self, url: str, params: dict | None = None, retries: int = 3) -> Any:
        """
        Make a GET request with rate-limit-aware retry logic.

        Handles 403/429 (rate limit) and 5xx errors.
        """
        for attempt in range(retries):
            try:
                resp = self._session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                logger.warning(f"Request failed ({attempt+1}/{retries}): {exc}")
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (403, 429):
                # Check rate limit headers
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(1, reset - int(time.time()) + 5)
                logger.warning(f"Rate limit hit. Waiting {wait}s before retry.")
                time.sleep(min(wait, 120))
                continue

            if resp.status_code == 404:
                logger.warning(f"404 Not Found: {url}")
                return None

            if resp.status_code >= 500:
                logger.warning(f"Server error {resp.status_code}. Retry {attempt+1}/{retries}")
                time.sleep(2 ** attempt)
                continue

            logger.error(f"Unexpected HTTP {resp.status_code} for {url}")
            return None

        logger.error(f"All {retries} retries failed for: {url}")
        return None

    def fetch_issues(
        self,
        repo: str,
        state: str = "closed",
        labels: list[str] | None = None,
        max_pages: int = 5,
        per_page: int = 30,
        skip_prs: bool = True,
        min_body_length: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch issues from a GitHub repository.

        Args:
            repo: "owner/repo" format
            state: "open", "closed", or "all"
            labels: List of label names to filter by (empty = all)
            max_pages: Maximum pages to fetch
            per_page: Issues per page (max 100)
            skip_prs: Skip pull requests (recommended)
            min_body_length: Skip issues with body shorter than this

        Returns:
            List of normalized issue dicts
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
        issues: list[dict[str, Any]] = []

        params: dict[str, Any] = {
            "state": state,
            "per_page": min(per_page, 100),
            "direction": "desc",
            "sort": "updated",
        }
        if labels:
            params["labels"] = ",".join(labels)

        for page in range(1, max_pages + 1):
            params["page"] = page
            logger.info(f"Fetching {repo} issues page {page}/{max_pages}")
            data = self._get(url, params=params)

            if not data:
                break

            if not isinstance(data, list) or len(data) == 0:
                break

            for item in data:
                # Skip PRs
                if skip_prs and "pull_request" in item:
                    continue

                # Skip too-short bodies
                body = item.get("body") or ""
                if len(body.strip()) < min_body_length:
                    continue

                issues.append(self._normalize_issue(item, repo))

            # If we got fewer items than per_page, we're on the last page
            if len(data) < params["per_page"]:
                break

        logger.info(f"Fetched {len(issues)} issues from {repo}")
        return issues

    def fetch_issue_comments(self, repo: str, issue_number: int) -> list[dict]:
        """Fetch comments for a specific issue."""
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}/comments"
        data = self._get(url, params={"per_page": 50})
        if not data:
            return []
        return [
            {
                "author": c.get("user", {}).get("login", ""),
                "body": c.get("body", ""),
                "created_at": c.get("created_at", ""),
            }
            for c in data
        ]

    def get_repo_info(self, repo: str) -> dict[str, Any] | None:
        """Fetch basic repository metadata."""
        url = f"{GITHUB_API_BASE}/repos/{repo}"
        return self._get(url)

    @staticmethod
    def _normalize_issue(raw: dict, repo: str) -> dict[str, Any]:
        """Normalize a raw GitHub issue dict to our schema."""
        labels = [lb.get("name", "") for lb in raw.get("labels", [])]
        return {
            "id": f"{repo}#{raw.get('number', 0)}",
            "repo": repo,
            "number": raw.get("number", 0),
            "title": raw.get("title", "").strip(),
            "body": (raw.get("body") or "").strip(),
            "state": raw.get("state", ""),
            "labels": labels,
            "created_at": raw.get("created_at", ""),
            "updated_at": raw.get("updated_at", ""),
            "closed_at": raw.get("closed_at", ""),
            "comments_count": raw.get("comments", 0),
            "url": raw.get("html_url", ""),
        }

    def check_rate_limit(self) -> dict[str, Any]:
        """Return current rate limit status."""
        data = self._get(f"{GITHUB_API_BASE}/rate_limit")
        if data:
            return data.get("rate", {})
        return {}
