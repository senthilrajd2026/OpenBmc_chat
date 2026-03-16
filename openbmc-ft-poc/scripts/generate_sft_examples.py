#!/usr/bin/env python3
"""
Generate SFT (supervised fine-tuning) examples for openbmc-ft-poc.

Reads from all intermediate sources (chunks, issues, services, D-Bus strings)
and uses the configured LLM provider to generate structured training examples.

Usage:
    python3 scripts/generate_sft_examples.py [--provider mock] [--limit 100]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.example_generation import get_provider
from openbmc_ft_poc.issue_transform import transform_issues_batch
from openbmc_ft_poc.logging_utils import setup_logging, get_logger
from openbmc_ft_poc.prompt_templates import (
    INSUFFICIENT_EVIDENCE_PROMPT,
    SYSTEM_INSTRUCTION,
    format_dbus_prompt,
    format_doc_chunk_prompt,
    format_issue_prompt,
    format_service_prompt,
)

setup_logging()
logger = get_logger(__name__)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SFT examples")
    parser.add_argument(
        "--provider", default=None,
        help="LLM provider: mock, openai, anthropic, local (overrides config)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum total examples to generate"
    )
    parser.add_argument(
        "--insufficient-count", type=int, default=20,
        help="Number of insufficient-evidence examples to generate"
    )
    args = parser.parse_args()

    cfg = get_config()
    cfg.ensure_dirs()

    provider_name = args.provider or cfg.llm_provider
    provider = get_provider(provider_name, seed=cfg.seed)
    logger.info(f"Using LLM provider: {provider_name}")

    out_dir = cfg.data_intermediate / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generated_examples.jsonl"

    rng = random.Random(cfg.seed)
    examples: list[dict] = []
    rpm_delay = 60.0 / cfg.settings["llm"].get("requests_per_minute", 20)

    def generate_one(prompt: str) -> dict | None:
        text = provider.generate(prompt, system=SYSTEM_INSTRUCTION)
        if not text:
            return None
        parsed = provider.parse_json_output(text)
        return parsed

    # ------------------------------------------------------------------
    # 1. Doc chunks
    # ------------------------------------------------------------------
    chunks_path = cfg.data_intermediate / "all_chunks.jsonl"
    chunks = load_jsonl(chunks_path)
    logger.info(f"Loaded {len(chunks)} doc chunks")

    # Prioritize chunks with pattern candidates
    has_patterns = [c for c in chunks if c.get("pattern_candidates")]
    no_patterns = [c for c in chunks if not c.get("pattern_candidates")]

    rng.shuffle(has_patterns)
    rng.shuffle(no_patterns)
    # Use 70% pattern-tagged, 30% untagged
    chunk_sample = has_patterns[:int(len(has_patterns) * 0.8)] + no_patterns[:50]
    rng.shuffle(chunk_sample)

    target_from_docs = (args.limit or 500) // 2
    logger.info(f"Generating up to {target_from_docs} examples from doc chunks")

    for i, chunk in enumerate(chunk_sample[:target_from_docs]):
        patterns = chunk.get("pattern_candidates", [])
        pattern = patterns[0] if patterns else "general"
        subsystem = chunk.get("subsystem", "")

        prompt = format_doc_chunk_prompt(chunk, pattern=pattern, subsystem=subsystem)
        ex = generate_one(prompt)
        if ex and "instruction" in ex and "output" in ex:
            examples.append(ex)

        if i % 20 == 0:
            logger.info(f"Doc chunks: {i}/{min(len(chunk_sample), target_from_docs)} processed, {len(examples)} examples so far")

        if provider_name != "mock":
            time.sleep(rpm_delay)

    # ------------------------------------------------------------------
    # 2. GitHub issues
    # ------------------------------------------------------------------
    issues_dir = cfg.data_intermediate / "issues"
    all_issues: list[dict] = []
    for f in issues_dir.glob("*.jsonl") if issues_dir.exists() else []:
        all_issues.extend(load_jsonl(f))

    logger.info(f"Loaded {len(all_issues)} raw issues")
    issue_signals = transform_issues_batch(all_issues, cfg.debug_patterns, cfg.subsystems)
    rng.shuffle(issue_signals)

    target_from_issues = (args.limit or 500) // 4
    logger.info(f"Generating up to {target_from_issues} examples from issues")

    for i, signal in enumerate(issue_signals[:target_from_issues]):
        prompt = format_issue_prompt(signal)
        ex = generate_one(prompt)
        if ex and "instruction" in ex and "output" in ex:
            examples.append(ex)

        if i % 10 == 0:
            logger.info(f"Issues: {i}/{min(len(issue_signals), target_from_issues)} processed")

        if provider_name != "mock":
            time.sleep(rpm_delay)

    # ------------------------------------------------------------------
    # 3. Service unit examples
    # ------------------------------------------------------------------
    services_dir = cfg.data_intermediate / "services"
    all_services: list[dict] = []
    for f in services_dir.glob("*.jsonl") if services_dir.exists() else []:
        all_services.extend(load_jsonl(f))

    rng.shuffle(all_services)
    target_from_services = min(50, len(all_services))
    logger.info(f"Generating up to {target_from_services} examples from service units")

    for i, svc in enumerate(all_services[:target_from_services]):
        prompt = format_service_prompt(svc)
        ex = generate_one(prompt)
        if ex and "instruction" in ex and "output" in ex:
            examples.append(ex)

        if provider_name != "mock":
            time.sleep(rpm_delay)

    # ------------------------------------------------------------------
    # 4. D-Bus interface examples
    # ------------------------------------------------------------------
    dbus_dir = cfg.data_intermediate / "dbus"
    all_dbus: list[dict] = []
    for f in dbus_dir.glob("*.jsonl") if dbus_dir.exists() else []:
        raw = load_jsonl(f)
        # Focus on interface strings, not paths
        all_dbus.extend([d for d in raw if d.get("kind") == "interface"])

    rng.shuffle(all_dbus)
    target_from_dbus = min(50, len(all_dbus))
    logger.info(f"Generating up to {target_from_dbus} examples from D-Bus interfaces")

    for i, dbus in enumerate(all_dbus[:target_from_dbus]):
        prompt = format_dbus_prompt(dbus)
        ex = generate_one(prompt)
        if ex and "instruction" in ex and "output" in ex:
            examples.append(ex)

        if provider_name != "mock":
            time.sleep(rpm_delay)

    # ------------------------------------------------------------------
    # 5. Insufficient evidence examples (synthetic)
    # ------------------------------------------------------------------
    logger.info(f"Generating {args.insufficient_count} insufficient-evidence examples")
    for _ in range(args.insufficient_count):
        ex = generate_one(INSUFFICIENT_EVIDENCE_PROMPT)
        if ex and "instruction" in ex and "output" in ex:
            examples.append(ex)

        if provider_name != "mock":
            time.sleep(rpm_delay)

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    with out_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    logger.info(f"Generated {len(examples)} total examples → {out_path}")
    print(f"\nGenerated {len(examples)} examples")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
