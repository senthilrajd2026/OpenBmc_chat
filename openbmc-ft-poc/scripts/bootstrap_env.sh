#!/usr/bin/env bash
# =========================================================
# Bootstrap environment for openbmc-ft-poc
# Supports: WSL2 Ubuntu, native Ubuntu 24.04
#
# Usage:
#   bash scripts/bootstrap_env.sh [--skip-gpu] [--dry-run]
# =========================================================

set -euo pipefail

SKIP_GPU=false
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --skip-gpu) SKIP_GPU=true ;;
        --dry-run) DRY_RUN=true ;;
    esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
run() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        log "[dry-run] $*"
    else
        log "Running: $*"
        "$@"
    fi
}

# ------------------------------------------------------------------
# Detect environment
# ------------------------------------------------------------------
IS_WSL=false
IS_LINUX=false

if grep -qi "microsoft" /proc/version 2>/dev/null || uname -r | grep -qi "wsl"; then
    IS_WSL=true
    log "Detected: WSL2 Ubuntu"
elif [[ "$(uname -s)" == "Linux" ]]; then
    IS_LINUX=true
    log "Detected: Native Linux"
else
    log "WARNING: Unsupported platform. This script supports WSL2 Ubuntu and native Ubuntu 24.04."
fi

# Distro check
if command -v lsb_release &>/dev/null; then
    DISTRO=$(lsb_release -is 2>/dev/null || echo "unknown")
    VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")
    log "Distro: ${DISTRO} ${VERSION}"

    if [[ "${DISTRO}" != "Ubuntu" ]]; then
        log "WARNING: This script is designed for Ubuntu. Other distros may need adjustment."
    fi
fi

# ------------------------------------------------------------------
# Python 3.11 check
# ------------------------------------------------------------------
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' || echo "")
log "Python version: ${PYTHON_VERSION}"

if ! python3 -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then
    log "Python 3.11+ required. Installing..."
    run sudo apt-get update -qq
    run sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
    log "Setting python3 to python3.11..."
    run sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
fi

# ------------------------------------------------------------------
# System packages
# ------------------------------------------------------------------
log "Installing system packages..."
run sudo apt-get update -qq
run sudo apt-get install -y \
    git \
    git-lfs \
    curl \
    wget \
    build-essential \
    python3-dev \
    python3-pip \
    python3-venv \
    libssl-dev \
    libffi-dev \
    2>/dev/null || log "WARNING: Some packages may not have installed. Check manually."

# ------------------------------------------------------------------
# Python virtual environment
# ------------------------------------------------------------------
VENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/venv"
if [[ ! -d "${VENV_DIR}" ]]; then
    log "Creating Python virtual environment at ${VENV_DIR}..."
    run python3 -m venv "${VENV_DIR}"
fi

log "Activating virtual environment..."
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate" 2>/dev/null || true

# ------------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------------
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log "Installing Python requirements..."
run pip install --upgrade pip setuptools wheel
run pip install -r "${PROJ_DIR}/requirements.txt"
run pip install -e "${PROJ_DIR}"

# ------------------------------------------------------------------
# GPU setup (optional)
# ------------------------------------------------------------------
if [[ "${SKIP_GPU}" == "false" ]]; then
    if command -v nvidia-smi &>/dev/null; then
        log "NVIDIA GPU detected:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true

        log "Install GPU/training dependencies? (requires CUDA toolkit)"
        log "To install training deps: pip install torch transformers peft bitsandbytes accelerate axolotl"
        log "(Skipping auto-install of GPU packages; install manually with the above command)"
    else
        log "No NVIDIA GPU detected. Dataset generation will work without GPU."
        log "For fine-tuning, you will need a CUDA-capable GPU."
    fi
fi

# ------------------------------------------------------------------
# .env setup
# ------------------------------------------------------------------
ENV_FILE="${PROJ_DIR}/.env"
ENV_EXAMPLE="${PROJ_DIR}/.env.example"
if [[ ! -f "${ENV_FILE}" ]]; then
    log "Creating .env from .env.example..."
    run cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    log "IMPORTANT: Edit .env and set your GITHUB_TOKEN for issue fetching."
else
    log ".env already exists; skipping."
fi

# ------------------------------------------------------------------
# Data directories
# ------------------------------------------------------------------
log "Creating data directories..."
run mkdir -p \
    "${PROJ_DIR}/data/raw/repos" \
    "${PROJ_DIR}/data/intermediate/chunks" \
    "${PROJ_DIR}/data/intermediate/issues" \
    "${PROJ_DIR}/data/intermediate/services" \
    "${PROJ_DIR}/data/intermediate/dbus" \
    "${PROJ_DIR}/data/intermediate/examples" \
    "${PROJ_DIR}/data/processed" \
    "${PROJ_DIR}/data/reports" \
    "${PROJ_DIR}/data/logs" \
    "${PROJ_DIR}/outputs"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
log ""
log "Bootstrap complete!"
log ""
log "Next steps:"
log "  1. Edit .env and set GITHUB_TOKEN"
log "  2. Run environment check: python3 scripts/check_env.py"
log "  3. Clone OpenBMC repos:   make clone"
log "  4. Fetch GitHub issues:   make fetch-issues"
log "  5. Parse sources:         make parse"
log "  6. Generate dataset:      make generate"
log "  7. Validate & split:      make validate && make split"
log "  8. Train (with GPU):      make train-lora"
log ""
log "Or run the full data pipeline at once: make pipeline"
