"""
Document chunking for openbmc-ft-poc.

Splits documents primarily by heading, then by size.
Preserves source metadata for downstream use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .logging_utils import get_logger

logger = get_logger(__name__)

# Regex to detect markdown headings (## Heading, ### Heading)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Approximate tokens per word (safe estimate for English text)
_WORDS_PER_TOKEN = 0.75


def _word_count(text: str) -> int:
    return len(text.split())


def _est_tokens(text: str) -> int:
    return int(_word_count(text) / _WORDS_PER_TOKEN)


@dataclass
class Chunk:
    """A piece of a document with its metadata."""

    chunk_id: str
    source_id: str
    repo: str
    path: str
    heading: str
    level: int            # heading depth (1-6, 0 = no heading)
    content: str
    tokens_est: int
    subsystem: str = ""
    pattern_candidates: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "repo": self.repo,
            "path": self.path,
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "tokens_est": self.tokens_est,
            "subsystem": self.subsystem,
            "pattern_candidates": self.pattern_candidates,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        return cls(
            chunk_id=d["chunk_id"],
            source_id=d["source_id"],
            repo=d["repo"],
            path=d["path"],
            heading=d["heading"],
            level=d["level"],
            content=d["content"],
            tokens_est=d["tokens_est"],
            subsystem=d.get("subsystem", ""),
            pattern_candidates=d.get("pattern_candidates", []),
            extra={k: v for k, v in d.items() if k not in (
                "chunk_id", "source_id", "repo", "path", "heading",
                "level", "content", "tokens_est", "subsystem", "pattern_candidates"
            )},
        )


def split_by_headings(
    text: str,
    source_id: str,
    repo: str,
    path: str,
    max_tokens: int = 400,
    min_tokens: int = 30,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """
    Split a markdown document into chunks.

    Strategy:
    1. Split on headings first (preserves logical sections)
    2. If a section is larger than max_tokens, split further by paragraphs
    3. If a section is smaller than min_tokens, merge with next

    Args:
        text: Full document text
        source_id: Unique source identifier
        repo: Repository name
        path: File path within repo
        max_tokens: Maximum estimated tokens per chunk
        min_tokens: Minimum tokens to keep a chunk
        overlap_tokens: Overlap tokens between oversized splits (not used in heading split)

    Returns:
        List of Chunk objects
    """
    sections = _extract_sections(text)
    chunks: list[Chunk] = []
    chunk_idx = 0

    for section in sections:
        heading_text = section["heading"]
        heading_level = section["level"]
        body = section["body"]

        if _est_tokens(body) <= max_tokens:
            body_stripped = body.strip()
            if body_stripped and (_est_tokens(body_stripped) >= min_tokens or heading_text):
                chunk_idx += 1
                chunk = Chunk(
                    chunk_id=f"{source_id}::{chunk_idx:04d}",
                    source_id=source_id,
                    repo=repo,
                    path=path,
                    heading=heading_text,
                    level=heading_level,
                    content=body.strip(),
                    tokens_est=_est_tokens(body),
                )
                chunks.append(chunk)
        else:
            # Split large section by paragraphs
            sub_chunks = _split_by_paragraphs(
                body, max_tokens=max_tokens, min_tokens=min_tokens
            )
            for sub in sub_chunks:
                chunk_idx += 1
                chunk = Chunk(
                    chunk_id=f"{source_id}::{chunk_idx:04d}",
                    source_id=source_id,
                    repo=repo,
                    path=path,
                    heading=heading_text,
                    level=heading_level,
                    content=sub.strip(),
                    tokens_est=_est_tokens(sub),
                )
                chunks.append(chunk)

    logger.debug(f"Chunked {path}: {len(chunks)} chunks")
    return chunks


def _extract_sections(text: str) -> list[dict]:
    """
    Extract heading + body pairs from markdown text.

    Returns list of dicts: {heading, level, body}
    """
    sections = []
    lines = text.splitlines(keepends=True)
    current_heading = ""
    current_level = 0
    current_body_lines: list[str] = []

    for line in lines:
        m = _HEADING_RE.match(line.rstrip())
        if m:
            # Save current section
            if current_body_lines or current_heading:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "body": "".join(current_body_lines).strip(),
                })
            current_heading = m.group(2).strip()
            current_level = len(m.group(1))
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Save last section
    if current_body_lines or current_heading:
        sections.append({
            "heading": current_heading,
            "level": current_level,
            "body": "".join(current_body_lines).strip(),
        })

    # If no headings found, treat whole doc as one section
    if not sections or all(not s["heading"] and not s["body"] for s in sections):
        body = text.strip()
        if body:
            sections = [{"heading": "", "level": 0, "body": body}]
        else:
            sections = []

    return sections


def _split_by_paragraphs(
    text: str, max_tokens: int, min_tokens: int
) -> list[str]:
    """Split text by double newlines (paragraphs), respecting max_tokens."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        pt = _est_tokens(para)

        if current_tokens + pt > max_tokens and current_parts:
            combined = "\n\n".join(current_parts)
            if _est_tokens(combined) >= min_tokens:
                chunks.append(combined)
            current_parts = [para]
            current_tokens = pt
        else:
            current_parts.append(para)
            current_tokens += pt

    if current_parts:
        combined = "\n\n".join(current_parts)
        if _est_tokens(combined) >= min_tokens:
            chunks.append(combined)

    return chunks if chunks else [text]


def infer_subsystem(text: str, subsystems: list[dict]) -> str:
    """
    Infer the most likely OpenBMC subsystem from text.

    Matches aliases from the subsystems config.
    Returns subsystem id or empty string if no match.
    """
    text_lower = text.lower()
    best: tuple[str, int] = ("", 0)

    for sub in subsystems:
        count = 0
        for alias in sub.get("aliases", []):
            count += text_lower.count(alias.lower())
        if count > best[1]:
            best = (sub["id"], count)

    return best[0] if best[1] > 0 else ""


def infer_patterns(text: str, patterns: list[dict]) -> list[str]:
    """
    Infer matching debug patterns from text content.

    Returns list of pattern ids that have keyword matches.
    """
    text_lower = text.lower()
    matched: list[str] = []

    for pat in patterns:
        for kw in pat.get("keywords", []):
            if kw.lower() in text_lower:
                matched.append(pat["id"])
                break

    return matched
