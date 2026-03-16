#!/usr/bin/env python3
"""
Parse documentation files from cloned OpenBMC repos.

Chunks docs by heading, tags subsystem and debug patterns,
outputs chunk JSONL to data/intermediate/chunks/.

Usage:
    python3 scripts/parse_docs.py [--repo openbmc-docs]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.chunking import infer_patterns, infer_subsystem, split_by_headings
from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.source_loader import find_doc_files

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse OpenBMC documentation files")
    parser.add_argument("--repo", help="Only parse this repo id")
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()
    out_dir = cfg.data_intermediate / "chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    chunk_settings = cfg.settings.get("chunking", {})
    max_tokens = chunk_settings.get("max_chunk_tokens", 400)
    min_tokens = chunk_settings.get("min_chunk_tokens", 30)
    overlap_tokens = chunk_settings.get("overlap_tokens", 50)

    total_chunks = 0

    for repo_cfg in cfg.repos:
        if args.repo and repo_cfg["id"] != args.repo:
            continue
        if not repo_cfg.get("parse_docs", True):
            continue

        repo_path = cfg.project_root / repo_cfg["local_path"]
        if not repo_path.exists():
            logger.warning(f"Repo not found at {repo_path}; skipping (run 'make clone' first)")
            continue

        doc_files = find_doc_files(
            repo_path,
            extensions=repo_cfg.get("doc_extensions", [".md", ".rst", ".txt"]),
            subdirs=repo_cfg.get("doc_subdirs"),
        )

        logger.info(f"Parsing {len(doc_files)} doc files from {repo_cfg['id']}")
        repo_chunks = []

        for doc_file in doc_files:
            try:
                text = doc_file.read_text(encoding="utf-8", errors="replace")
                rel_path = str(doc_file.relative_to(repo_path))
                source_id = f"{repo_cfg['id']}::{rel_path}"

                chunks = split_by_headings(
                    text=text,
                    source_id=source_id,
                    repo=repo_cfg["id"],
                    path=rel_path,
                    max_tokens=max_tokens,
                    min_tokens=min_tokens,
                    overlap_tokens=overlap_tokens,
                )

                # Tag each chunk with subsystem and pattern candidates
                for chunk in chunks:
                    combined_text = f"{chunk.heading} {chunk.content}"
                    chunk.subsystem = infer_subsystem(combined_text, cfg.subsystems)
                    chunk.pattern_candidates = infer_patterns(combined_text, cfg.debug_patterns)
                    repo_chunks.append(chunk.to_dict())

            except Exception as exc:
                logger.warning(f"Failed to parse {doc_file}: {exc}")

        # Write to JSONL
        out_path = out_dir / f"chunks_{repo_cfg['id']}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for chunk in repo_chunks:
                fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        logger.info(f"Wrote {len(repo_chunks)} chunks from {repo_cfg['id']} to {out_path}")
        total_chunks += len(repo_chunks)

    print(f"\nTotal chunks generated: {total_chunks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
