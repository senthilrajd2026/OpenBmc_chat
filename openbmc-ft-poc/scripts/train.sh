#!/usr/bin/env bash
# =========================================================
# Training script for openbmc-ft-poc
# Supports LoRA and QLoRA modes
# Works in WSL2 Ubuntu and native Ubuntu 24.04
#
# Usage:
#   bash scripts/train.sh lora
#   bash scripts/train.sh qlora
#   bash scripts/train.sh lora --dry-run
# =========================================================

set -euo pipefail

MODE="${1:-lora}"
DRY_RUN="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/data/logs"
mkdir -p "${LOG_DIR}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ------------------------------------------------------------------
# Environment check
# ------------------------------------------------------------------
log "Checking environment..."
python3 "${SCRIPT_DIR}/check_env.py" || {
    log "WARNING: Environment check reported issues. Check output above."
}

# Check CUDA
if ! python3 -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" 2>/dev/null; then
    log "ERROR: CUDA not available. Fine-tuning requires a CUDA-capable GPU."
    log "       For dataset generation only, skip training with 'make pipeline'."
    exit 1
fi

# Check Axolotl
if ! python3 -c "import axolotl" 2>/dev/null; then
    log "ERROR: Axolotl not installed."
    log "Install training dependencies:"
    log "  pip install axolotl torch transformers peft bitsandbytes accelerate"
    exit 1
fi

# ------------------------------------------------------------------
# Select config
# ------------------------------------------------------------------
case "${MODE}" in
    lora)
        CONFIG="${PROJECT_ROOT}/axolotl/openbmc-lora-1b.yml"
        log "Using LoRA config: ${CONFIG}"
        ;;
    qlora)
        CONFIG="${PROJECT_ROOT}/axolotl/openbmc-qlora-1b.yml"
        log "Using QLoRA config: ${CONFIG}"
        ;;
    *)
        log "ERROR: Unknown mode '${MODE}'. Use 'lora' or 'qlora'."
        exit 1
        ;;
esac

# Check dataset exists
if [[ ! -f "${PROJECT_ROOT}/data/train.jsonl" ]]; then
    log "ERROR: data/train.jsonl not found."
    log "Run 'make pipeline' to generate the dataset first."
    exit 1
fi

TRAIN_COUNT=$(wc -l < "${PROJECT_ROOT}/data/train.jsonl" 2>/dev/null || echo 0)
log "Training set: ${TRAIN_COUNT} examples"

if [[ "${TRAIN_COUNT}" -lt 50 ]]; then
    log "WARNING: Very small training set (${TRAIN_COUNT} examples). Results may be poor."
fi

# ------------------------------------------------------------------
# Dry run
# ------------------------------------------------------------------
if [[ "${DRY_RUN}" == "--dry-run" ]]; then
    log "DRY RUN: would execute:"
    log "  axolotl train ${CONFIG}"
    exit 0
fi

# ------------------------------------------------------------------
# Training
# ------------------------------------------------------------------
LOG_FILE="${LOG_DIR}/train_${MODE}_$(date '+%Y%m%d_%H%M%S').log"
log "Starting ${MODE} training → log: ${LOG_FILE}"
log "GPU info:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || true

cd "${PROJECT_ROOT}"
python3 -m axolotl.cli.train "${CONFIG}" 2>&1 | tee "${LOG_FILE}"

EXIT_CODE=${PIPESTATUS[0]}
if [[ ${EXIT_CODE} -eq 0 ]]; then
    log "Training completed successfully."
    log "Model output: outputs/openbmc-${MODE}-1b/"
else
    log "ERROR: Training failed with exit code ${EXIT_CODE}"
    log "Check log: ${LOG_FILE}"
    exit ${EXIT_CODE}
fi
