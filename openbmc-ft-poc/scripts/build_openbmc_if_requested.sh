#!/usr/bin/env bash
# =========================================================
# Optional OpenBMC build support for openbmc-ft-poc
#
# This is a secondary, optional script. The dataset pipeline
# continues even if this step is skipped or fails.
#
# Usage:
#   bash scripts/build_openbmc_if_requested.sh --check-only
#   bash scripts/build_openbmc_if_requested.sh --dry-run
#   bash scripts/build_openbmc_if_requested.sh --machine qemuarm
# =========================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/data/logs"
mkdir -p "${LOG_DIR}"

CHECK_ONLY=false
DRY_RUN=false
MACHINE="qemuarm"

for arg in "$@"; do
    case "$arg" in
        --check-only) CHECK_ONLY=true ;;
        --dry-run) DRY_RUN=true ;;
        --machine=*) MACHINE="${arg#*=}" ;;
        --machine) shift; MACHINE="$1" ;;
    esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Run precheck via Python build_support module
log "Running OpenBMC build precheck..."
python3 - <<PYEOF
import sys
sys.path.insert(0, "${PROJECT_ROOT}/src")
from openbmc_ft_poc.build_support import run_build_precheck
from openbmc_ft_poc.env_detect import detect_environment
from pathlib import Path
import json

env = detect_environment()
repo_path = Path("${PROJECT_ROOT}/data/raw/repos/openbmc")
result = run_build_precheck(env, repo_path)

print(json.dumps(result, indent=2))

if not result["can_build"]:
    print("\nBlocKERS (build cannot proceed):")
    for b in result["blockers"]:
        print(f"  ✗  {b}")
    sys.exit(1)
else:
    print("\nBuild precheck PASSED")
    sys.exit(0)
PYEOF

PRECHECK_RC=$?

if [[ ${PRECHECK_RC} -ne 0 ]]; then
    log "Build precheck FAILED. Cannot proceed with build."
    log "This is an optional step. Dataset pipeline continues normally."
    exit 0   # Non-fatal: rest of pipeline is unaffected
fi

if [[ "${CHECK_ONLY}" == "true" ]]; then
    log "Check-only mode; skipping actual build."
    exit 0
fi

# ------------------------------------------------------------------
# Attempt build
# ------------------------------------------------------------------
REPO_PATH="${PROJECT_ROOT}/data/raw/repos/openbmc"

if [[ ! -d "${REPO_PATH}" ]]; then
    log "ERROR: OpenBMC repo not found at ${REPO_PATH}"
    log "Run 'make clone' first."
    exit 0   # Non-fatal
fi

LOG_FILE="${LOG_DIR}/build_${MACHINE}_$(date '+%Y%m%d_%H%M%S').log"
log "Starting OpenBMC build: MACHINE=${MACHINE}, dry_run=${DRY_RUN}"
log "Log: ${LOG_FILE}"

if [[ "${DRY_RUN}" == "true" ]]; then
    log "[dry-run] Would run: cd ${REPO_PATH} && . setup ${MACHINE} build && bitbake obmc-phosphor-image"
    exit 0
fi

# Actual build (runs in a subshell to avoid polluting current env)
(
    cd "${REPO_PATH}" || exit 1
    # shellcheck disable=SC1091
    . setup "${MACHINE}" build 2>&1 | tee -a "${LOG_FILE}" || {
        log "ERROR: setup script failed. Check ${LOG_FILE}"
        exit 1
    }
    bitbake obmc-phosphor-image 2>&1 | tee -a "${LOG_FILE}"
) || BUILD_RC=$?

BUILD_RC=${BUILD_RC:-0}

if [[ ${BUILD_RC} -eq 0 ]]; then
    log "Build completed successfully!"
else
    log "Build FAILED with exit code ${BUILD_RC}"
    log "Summarizing build errors..."
    python3 "${SCRIPT_DIR}/summarize_build_logs.py" --log-dir "${LOG_DIR}"
    log "Build failure is non-fatal for the dataset pipeline."
fi
