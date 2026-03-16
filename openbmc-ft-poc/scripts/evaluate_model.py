#!/usr/bin/env python3
"""
Evaluate fine-tuned model quality on eval set.

Runs inference on eval examples and scores outputs.
Requires trained model artifacts in outputs/openbmc-{lora|qlora}-1b/.

Usage:
    python3 scripts/evaluate_model.py --model-dir outputs/openbmc-lora-1b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openbmc_ft_poc.config import get_config
from openbmc_ft_poc.dataset_builder import read_jsonl
from openbmc_ft_poc.evaluation import evaluate_dataset, print_eval_report, score_example
from openbmc_ft_poc.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def load_model_and_tokenizer(model_dir: str):
    """Load a PEFT LoRA/QLoRA model for inference."""
    try:
        import torch  # type: ignore
        from peft import PeftModel  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except ImportError as exc:
        logger.error(f"Training dependencies not installed: {exc}")
        logger.info("Install training deps: pip install torch transformers peft bitsandbytes")
        return None, None

    model_path = Path(model_dir)
    if not model_path.exists():
        logger.error(f"Model directory not found: {model_dir}")
        return None, None

    logger.info(f"Loading model from {model_dir}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
        base_model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"  # default; override if needed

        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        model = PeftModel.from_pretrained(model, model_dir)
        model.eval()
        return model, tokenizer
    except Exception as exc:
        logger.error(f"Failed to load model: {exc}")
        return None, None


def run_inference(model, tokenizer, instruction: str, input_text: str = "") -> str:
    """Run inference with the fine-tuned model."""
    try:
        import torch  # type: ignore
    except ImportError:
        return ""

    # Alpaca-style prompt
    if input_text:
        prompt = (
            f"### Instruction:\n{instruction}\n\n"
            f"### Input:\n{input_text}\n\n"
            f"### Response:\n"
        )
    else:
        prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned model")
    parser.add_argument("--model-dir", required=True, help="Path to fine-tuned model directory")
    parser.add_argument("--eval-set", default=None, help="Eval JSONL path")
    parser.add_argument("--max-examples", type=int, default=50, help="Max examples to evaluate")
    parser.add_argument("--output", default=None, help="Save eval results to JSON")
    args = parser.parse_args()

    cfg = get_config()

    eval_path = Path(args.eval_set) if args.eval_set else cfg.eval_output
    if not eval_path.exists():
        logger.error(f"Eval set not found: {eval_path}")
        return 1

    eval_examples = read_jsonl(eval_path)[:args.max_examples]
    logger.info(f"Evaluating model on {len(eval_examples)} examples")

    model, tokenizer = load_model_and_tokenizer(args.model_dir)
    if model is None:
        logger.warning("Model not loaded; running evaluation on eval set answers only (no generation)")
        # Still useful: evaluate the ground truth eval set quality
        report = evaluate_dataset(eval_examples)
        print_eval_report(report)
        return 0

    # Run inference and score
    results = []
    for i, ex in enumerate(eval_examples):
        instruction = ex.get("instruction", "")
        input_text = ex.get("input", "")

        logger.info(f"Inference {i+1}/{len(eval_examples)}: {instruction[:60]}...")
        generated = run_inference(model, tokenizer, instruction, input_text)

        # Score the generated output
        fake_ex = {**ex, "output": generated}
        scores = score_example(fake_ex)

        results.append({
            "instruction": instruction,
            "reference_output": ex.get("output", ""),
            "generated_output": generated,
            "scores": scores,
        })

        if i % 10 == 0:
            avg_overall = sum(r["scores"]["overall"] for r in results) / len(results)
            logger.info(f"  Running avg overall score: {avg_overall:.3f}")

    # Aggregate
    avg_scores: dict[str, float] = {}
    dims = list(results[0]["scores"].keys()) if results else []
    for dim in dims:
        vals = [r["scores"][dim] for r in results]
        avg_scores[f"avg_{dim}"] = round(sum(vals) / len(vals), 3)

    print("\n" + "=" * 60)
    print("  Model Evaluation Results")
    print("=" * 60)
    for k, v in sorted(avg_scores.items()):
        bar = "█" * int(v * 20)
        print(f"  {k:<35} {v:.3f}  {bar}")
    print("=" * 60)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump({"results": results, "averages": avg_scores}, fh, indent=2)
        logger.info(f"Eval results saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
