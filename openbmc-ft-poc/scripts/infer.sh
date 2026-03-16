#!/usr/bin/env bash
# =========================================================
# Inference script for openbmc-ft-poc fine-tuned model
#
# Usage:
#   bash scripts/infer.sh [--model-dir outputs/openbmc-lora-1b] [--prompt "..."]
#   bash scripts/infer.sh --interactive
# =========================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL_DIR="${PROJECT_ROOT}/outputs/openbmc-lora-1b"
PROMPT=""
INTERACTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --prompt) PROMPT="$2"; shift 2 ;;
        --interactive) INTERACTIVE=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ ! -d "${MODEL_DIR}" ]]; then
    echo "ERROR: Model directory not found: ${MODEL_DIR}"
    echo "Run 'make train-lora' or 'make train-qlora' first."
    exit 1
fi

# Check dependencies
python3 -c "import torch, transformers, peft" 2>/dev/null || {
    echo "ERROR: Training/inference dependencies not installed."
    echo "Install: pip install torch transformers peft bitsandbytes"
    exit 1
}

if [[ "${INTERACTIVE}" == "true" ]]; then
    echo "OpenBMC FT PoC — Interactive Inference"
    echo "Model: ${MODEL_DIR}"
    echo "Type your question and press Enter. Ctrl+C to exit."
    echo ""

    python3 - <<'PYEOF'
import sys
sys.path.insert(0, "src")
import argparse, os
model_dir = os.environ.get("MODEL_DIR", "outputs/openbmc-lora-1b")

from openbmc_ft_poc.logging_utils import setup_logging
setup_logging(level="WARNING")

# Inline inference
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    base = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float16, device_map="auto")
    model = PeftModel.from_pretrained(model, model_dir)
    model.eval()

    while True:
        try:
            q = input("Question> ").strip()
            if not q:
                continue
            prompt = f"### Instruction:\n{q}\n\n### Response:\n"
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **inputs, max_new_tokens=512, temperature=0.7,
                    do_sample=True, pad_token_id=tokenizer.eos_token_id
                )
            resp = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            print(f"\n{resp}\n")
        except KeyboardInterrupt:
            print("\nBye.")
            break
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
PYEOF

elif [[ -n "${PROMPT}" ]]; then
    export MODEL_DIR="${MODEL_DIR}"
    python3 - <<PYEOF
import sys, os
sys.path.insert(0, "src")
model_dir = os.environ["MODEL_DIR"]
prompt_text = """${PROMPT}"""

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    base = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float16, device_map="auto")
    model = PeftModel.from_pretrained(model, model_dir)
    model.eval()

    prompt = f"### Instruction:\n{prompt_text}\n\n### Response:\n"
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=512, temperature=0.7,
            do_sample=True, pad_token_id=tokenizer.eos_token_id
        )
    resp = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    print(resp)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

else
    echo "Usage:"
    echo "  bash scripts/infer.sh --prompt 'Why is phosphor-ipmi-host failing to start?'"
    echo "  bash scripts/infer.sh --interactive"
    echo "  bash scripts/infer.sh --model-dir outputs/openbmc-qlora-1b --interactive"
    exit 0
fi
