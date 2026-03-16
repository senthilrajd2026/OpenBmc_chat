"""
Deduplication for openbmc-ft-poc training examples.

Uses TF-IDF cosine similarity to detect near-duplicate instructions.
Falls back to exact string dedup if sentence-transformers is unavailable.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.92


def exact_dedup(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove exact duplicate instructions using MD5 hash.

    Fast O(n) pass — always run before embedding-based dedup.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for ex in examples:
        key = hashlib.md5(ex.get("instruction", "").lower().strip().encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(ex)

    removed = len(examples) - len(unique)
    if removed:
        logger.info(f"Exact dedup removed {removed} exact duplicates")
    return unique


def tfidf_dedup(
    examples: list[dict[str, Any]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Near-duplicate removal using TF-IDF cosine similarity.

    Greedy O(n²) approach — suitable for datasets up to ~5000 examples.

    Args:
        examples: List of training examples
        threshold: Cosine similarity threshold above which examples are considered duplicates

    Returns:
        Deduplicated list
    """
    if not examples:
        return examples

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        logger.warning("sklearn not available; skipping TF-IDF dedup (exact dedup only)")
        return examples

    instructions = [ex.get("instruction", "") for ex in examples]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=10000,
        min_df=1,
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(instructions)
    except Exception as exc:
        logger.warning(f"TF-IDF vectorization failed: {exc}; skipping near-dedup")
        return examples

    n = len(examples)
    to_keep = [True] * n

    # Greedy: mark second occurrence as duplicate if similarity > threshold
    for i in range(n):
        if not to_keep[i]:
            continue
        # Only compare against remaining examples (guard empty slice)
        if i + 1 >= n:
            break
        sims = cosine_similarity(tfidf_matrix[i : i + 1], tfidf_matrix[i + 1 :]).flatten()
        for j_rel, sim in enumerate(sims):
            j = i + 1 + j_rel
            if sim >= threshold:
                to_keep[j] = False

    unique = [ex for ex, keep in zip(examples, to_keep) if keep]
    removed = n - len(unique)
    if removed:
        logger.info(
            f"TF-IDF dedup removed {removed} near-duplicates "
            f"(threshold={threshold})"
        )
    return unique


def deduplicate(
    examples: list[dict[str, Any]],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Full deduplication pipeline: exact then near-duplicate.

    Args:
        examples: Training examples
        similarity_threshold: TF-IDF cosine similarity cutoff

    Returns:
        Deduplicated examples
    """
    before = len(examples)
    examples = exact_dedup(examples)
    examples = tfidf_dedup(examples, threshold=similarity_threshold)
    after = len(examples)
    logger.info(f"Deduplication: {before} → {after} examples ({before - after} removed)")
    return examples
