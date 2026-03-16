# openbmc-ft-poc

**A minimal, powerful PoC for fine-tuning a small OpenBMC domain model that answers like a senior engineer.**

---

## What This Project Is

`openbmc-ft-poc` is a **fine-tuning-only** pipeline that produces a small (~1B parameter) OpenBMC domain model. The model is trained to answer like an **experienced OpenBMC firmware engineer** — not like a documentation bot.

This project focuses on:
- Senior OpenBMC engineer style answers
- Subsystem-aware reasoning
- Issue triage and diagnosis
- Debug method and sequence
- Command/check recommendations
- Fact vs hypothesis separation
- Evidence-driven diagnosis
- Asking for exact missing evidence
- Structured engineering answer format

This project does **not** implement RAG. A separate RAG project can be connected later.

---

## Why Fine-Tuning Only?

Most LLM applications for code/firmware Q&A rely on RAG (retrieval-augmented generation). This project intentionally separates concerns:

1. **Fine-tuning** teaches *how* to think like an engineer: diagnosis patterns, subsystem reasoning, structured output format, and appropriate use of evidence.
2. **RAG** (a future separate project) will inject *specific context*: platform configs, internal docs, live logs.

The model trained here learns the **reasoning style**. RAG will bring the **grounding context**. Separating them makes both easier to improve independently.

---

## Supported Environments

| Environment | Status |
|-------------|--------|
| WSL2 Ubuntu (Windows host) | Fully supported |
| Native Ubuntu 24.04 | Fully supported |
| macOS / other | Not supported (may partially work) |

### GPU Requirements (Training)

Training target: **NVIDIA RTX 2060 Super 8GB VRAM**

| Mode | VRAM needed | Status |
|------|-------------|--------|
| LoRA (8-bit) | ~5-6 GB | Supported |
| QLoRA (4-bit) | ~3-4 GB | Supported (recommended fallback) |

**Without a GPU**: You can still run the full dataset generation pipeline. Training is skipped. The pipeline continues normally.

---

## Quick Start

### Step 0 — CUDA and PyTorch setup (RTX 2060 Super)

The RTX 2060 Super uses the Turing architecture (compute capability 7.5).
It supports CUDA 11.x and 12.x but does **not** support bf16 (that needs Ampere / RTX 3xxx+).

```bash
# Check your CUDA driver version
nvidia-smi

# Install CUDA toolkit if not already installed (Ubuntu 24.04)
# For CUDA 12.1 (matches most recent driver):
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12-4

# Install PyTorch with CUDA 12.1 support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verify GPU is visible to PyTorch
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected: True  NVIDIA GeForce RTX 2060 SUPER

# Install Axolotl and training stack
pip install axolotl transformers peft bitsandbytes accelerate

# Verify bitsandbytes sees the GPU (needed for 8-bit/4-bit)
python3 -c "import bitsandbytes; print('bitsandbytes OK')"
```

> **WSL2 note**: If running on Windows with WSL2, CUDA works via the Windows NVIDIA driver — do NOT install a separate Linux CUDA driver inside WSL. Only install the CUDA toolkit (not the driver). The PyTorch install command above is the same.

### Step 1-6 — Full pipeline

```bash
# 1. Bootstrap the environment (installs Python deps, creates .env, data dirs)
bash scripts/bootstrap_env.sh

# 2. Edit .env and set your GitHub token
cp .env.example .env
nano .env   # set GITHUB_TOKEN=ghp_your_token_here

# 3. Check environment capabilities (confirms GPU visible)
python3 scripts/check_env.py

# 4. Run the full data pipeline (no GPU needed for this step)
make pipeline

# 5. (With GPU) Fine-tune — try LoRA first
make train-lora     # uses ~5-6GB VRAM on RTX 2060 Super
# If Out-of-Memory error occurs, fall back to QLoRA:
make train-qlora    # uses ~3-4GB VRAM

# 6. Run inference on the fine-tuned model
bash scripts/infer.sh --interactive
# or with a specific question:
bash scripts/infer.sh --prompt "The phosphor-ipmi-host service is stuck in activating state. Where do I start?"
```

---

## Full Project Structure

```
openbmc-ft-poc/
  README.md                   # This file
  requirements.txt            # Python dependencies
  pyproject.toml              # Package metadata
  .env.example                # Environment variable template
  Makefile                    # Pipeline orchestration

  configs/
    settings.yaml             # Global pipeline settings
    sources.yaml              # Data source definitions (repos, issues)
    dataset_rules.yaml        # Debug pattern taxonomy and validation rules

  axolotl/
    openbmc-lora-1b.yml       # LoRA training config (RTX 2060 Super)
    openbmc-qlora-1b.yml      # QLoRA training config (lower VRAM fallback)

  data/
    raw/                      # Cloned repos and raw fetched data
    intermediate/             # Parsed chunks, issues, service signals
    processed/                # Validated, deduped examples with metadata
    train.jsonl               # Axolotl-ready training set
    eval.jsonl                # Axolotl-ready evaluation set
    reports/                  # Dataset quality reports
    logs/                     # Pipeline and build logs

  scripts/                    # Executable pipeline scripts (see Pipeline Flow)
  src/openbmc_ft_poc/         # Core Python library
  prompts/                    # Generation prompt guidelines
  tests/                      # Unit tests
```

---

## Pipeline Flow

```
clone_sources.py        → Clones openbmc/openbmc, openbmc/docs repos
      ↓
fetch_github_issues.py  → Fetches closed issues from GitHub
      ↓
parse_docs.py           → Chunks markdown/rst docs by heading
parse_services.py       → Extracts systemd service unit signals
parse_dbus_strings.py   → Extracts xyz.openbmc_project.* interface strings
parse_logs_and_errors.py → Extracts log/error strings from C++ sources
chunk_sources.py        → Consolidates all chunks
      ↓
generate_sft_examples.py → Uses LLM provider to generate structured examples
      ↓
validate_examples.py    → Strict quality validation
dedupe_examples.py      → Removes exact and near-duplicate instructions
split_dataset.py        → Train/eval split with pattern diversity
      ↓
evaluate_dataset.py     → Dataset quality scoring
      ↓
train.sh                → Axolotl fine-tuning (GPU required)
infer.sh                → Inference on fine-tuned model
evaluate_model.py       → Post-training evaluation
```

---

## Dataset Generation

### LLM Provider Options

Set `LLM_PROVIDER` in `.env`:

| Provider | When to use |
|----------|------------|
| `mock` | Offline/testing — generates deterministic sample examples |
| `openai` | Production — GPT-4o-mini is cost-effective |
| `anthropic` | Production — Claude Haiku is cost-effective |
| `local` | Local Ollama/compatible — run on your own hardware |

```bash
# Mock mode (default, works offline)
python3 scripts/generate_sft_examples.py --provider mock

# With OpenAI
python3 scripts/generate_sft_examples.py --provider openai

# Limit output for testing
python3 scripts/generate_sft_examples.py --provider mock --limit 50
```

### Target Dataset Distribution

| Category | Target % |
|----------|----------|
| Debugging and triage | 45% |
| Subsystem classification | 25% |
| Command/check recommendation | 15% |
| Architecture explanation (engineer style) | 10% |
| Insufficient evidence / ask for more info | 5% |

### Example Model Output Format

For troubleshooting questions, the model produces:

```
**Assessment**
[1-3 sentences on likely subsystem involvement]

**Likely OpenBMC area**
[Specific subsystem name]

**Likely components/services**
- service or interface names

**Why this is likely**
[Reasoning from symptoms to hypothesis]

**Suggested checks/commands**
```bash
systemctl status <service>
journalctl -u <service> --no-pager -n 50
busctl tree <service>
```

**Missing evidence**
[Specific logs, paths, or data still needed]

**Confidence**
Medium — [brief explanation of confidence level]
```

---

## Debug Pattern Taxonomy

The dataset is built around 12 explicit debug patterns:

| Pattern | Description |
|---------|-------------|
| `service_state_debug` | Service failed/stuck/inactive |
| `dbus_lookup_debug` | ObjectMapper/D-Bus path not found |
| `sensor_debug` | Sensor missing, wrong value, not updating |
| `host_state_debug` | Host power/state transitions failing |
| `boot_progress_debug` | Boot stuck, POST failure |
| `event_logging_debug` | Log entries missing or wrong |
| `ipmi_debug` | IPMI command failures |
| `redfish_debug` | Redfish/bmcweb issues |
| `build_debug` | BitBake/Yocto build errors |
| `api_mapping_debug` | IPMI-to-D-Bus mapping issues |
| `insufficient_evidence` | Vague question — ask for more info |
| `cross_subsystem_debug` | Multi-service interaction issues |

---

## Training Configuration

### LoRA (Recommended first try)

File: `axolotl/openbmc-lora-1b.yml`

Key settings for RTX 2060 Super:
- `load_in_8bit: true` — halves VRAM vs fp32
- `sequence_len: 512` — keeps KV cache small
- `micro_batch_size: 1` + `gradient_accumulation_steps: 16`
- `gradient_checkpointing: true` — essential for 8GB
- `fp16: true` / `bf16: false` — RTX 2060 does not have bf16

### QLoRA (Lower VRAM fallback)

File: `axolotl/openbmc-qlora-1b.yml`

Key settings:
- `load_in_4bit: true` — NF4 quantization (~2x less VRAM than 8-bit)
- `optimizer: paged_adamw_8bit` — keeps optimizer states paged
- `lora_r: 32` — can afford higher rank at 4-bit

```bash
# Try LoRA first
make train-lora

# If OOM, switch to QLoRA
make train-qlora
```

---

## Hardware Expectations

### Dataset Generation (CPU only)
- RAM: 4GB minimum (8GB recommended)
- Disk: 10GB minimum for repos + intermediate data
- No GPU needed

### Fine-tuning (RTX 2060 Super 8GB)
- LoRA: ~5-6GB VRAM active during training
- QLoRA: ~3-4GB VRAM active during training
- Training time estimate: 1-3 hours for 1000 examples, 3 epochs

### Without GPU
The dataset pipeline runs fully without a GPU. Only the training and inference steps require a GPU. The pipeline continues gracefully:

```bash
make pipeline    # Works without GPU
make train-lora  # Requires CUDA — will warn and exit if not available
```

---

## Optional: OpenBMC Build Support

Build support is an optional secondary feature. It does not affect the dataset pipeline.

```bash
# Check if your system can build OpenBMC
make build-check

# Dry run (shows commands without executing)
make build-dry

# Attempt actual build (for qemuarm target)
bash scripts/build_openbmc_if_requested.sh --machine qemuarm
```

Build requirements:
- 8GB+ RAM
- 50GB+ free disk
- Ubuntu 22.04/24.04 with build-essential
- ~4+ CPU cores

The build step is safe to skip. The rest of the pipeline works without it.

---

## Future Expansion

### Adding Company/Private Repos

The `configs/sources.yaml` file has expansion stubs. To add a private repo:

```yaml
# configs/sources.yaml
repos:
  - id: my-company-bsp
    type: github_repo          # or company_repo adapter (future)
    url: https://github.com/my-company/openbmc-bsp
    local_path: data/raw/repos/my-company-bsp
    branch: main
    enabled: true
    parse_docs: true
    parse_services: true
    parse_dbus: true
```

The `src/openbmc_ft_poc/source_loader.py` `clone_or_update_repo()` function handles
any git URL. Private repo authentication is via standard git credential helpers or
SSH keys.

### Adding Internal Docs / Wikis

Future adapters planned (stubs in `sources.yaml`):
- `confluence` adapter for Confluence wikis
- `jira` adapter for Jira issue exports
- `internal_markdown` adapter for exported wiki markdown

### Connecting to a RAG System

The fine-tuned model is designed to accept injected context cleanly. The Alpaca-format `input` field is reserved for this purpose:

```python
# Future RAG integration pattern
instruction = "Sensor is not visible after reboot"
retrieved_context = rag_system.retrieve(instruction)

# Pass retrieved context in the 'input' field
response = model.generate(
    instruction=instruction,
    input=retrieved_context,   # injected by RAG
)
```

The training data already uses this pattern: the `input` field contains additional context (platform info, error snippets) separate from the main instruction.

---

## Makefile Reference

```
make setup          Install Python dependencies
make check          Detect environment capabilities
make clone          Clone OpenBMC source repos
make fetch-issues   Fetch GitHub issues
make parse          Parse all docs, services, D-Bus strings
make generate       Generate SFT examples
make validate       Validate and deduplicate examples
make split          Split into train/eval
make pipeline       Run full data pipeline (no training)
make train-lora     Fine-tune with LoRA
make train-qlora    Fine-tune with QLoRA
make infer          Run inference on fine-tuned model
make eval-dataset   Evaluate dataset quality
make eval-model     Evaluate model quality
make clean          Remove generated data (keep raw repos)
make test           Run unit tests
```

---

## Tests

```bash
# Run all tests
make test

# Run with coverage
pytest tests/ -v --cov=src/openbmc_ft_poc --cov-report=term-missing
```

---

## Design Decisions

### Why TinyLlama/1.1B?
- Fits in 8GB VRAM with LoRA/QLoRA
- Fast to fine-tune locally
- Sufficient capacity for structured output format learning
- Easy to replace with any other ~1B model (Qwen 0.5B, Phi-1.5, etc.)

### Why Alpaca format?
- Widely supported by Axolotl and other training frameworks
- Natural separation of instruction, context (input), and output
- Clean integration point for future RAG (context goes in `input`)

### Why not RAG in this PoC?
- RAG requires a vector database, embedding model, and retrieval pipeline
- Fine-tuning teaches the reasoning pattern; RAG provides the specific facts
- Separating them keeps each component clean and independently improvable

### Why subsystem-specific training?
- OpenBMC has distinct subsystems (D-Bus, IPMI, sensors, state manager, bmcweb)
- Generic LLMs mix up subsystem-specific commands and paths
- Targeted training produces much more useful and accurate debug guidance

---

## Troubleshooting Common RTX 2060 Super Issues

### Out of Memory during training
```bash
# Switch from LoRA to QLoRA
make train-qlora

# Or reduce gradient_accumulation_steps in axolotl/openbmc-qlora-1b.yml
# Change: gradient_accumulation_steps: 16
# To:     gradient_accumulation_steps: 8
```

### CUDA not detected by PyTorch
```bash
# Confirm driver is loaded
nvidia-smi

# Confirm PyTorch CUDA build matches your driver
python3 -c "import torch; print(torch.version.cuda)"
# Must match your CUDA driver version (or be ≤ driver version)

# If mismatch, reinstall torch for correct CUDA version
pip install torch --index-url https://download.pytorch.org/whl/cu118   # for CUDA 11.8
```

### `bitsandbytes` CUDA error
```bash
# RTX 2060 Super is sm_75 (Turing). Ensure bitsandbytes >= 0.41
pip install bitsandbytes --upgrade

# Test:
python3 -c "import bitsandbytes as bnb; print(bnb.__version__)"
```

### WSL2: GPU not visible
```bash
# Check GPU from WSL2
nvidia-smi    # should show your GPU

# If not visible, ensure:
# 1. Windows NVIDIA driver is 515+ (supports WSL2 CUDA)
# 2. Do NOT install a Linux NVIDIA driver inside WSL2
# 3. Add to /etc/wsl.conf inside WSL2:
#    [boot]
#    systemd=true

# Recommended .wslconfig on Windows host (in C:\Users\YourName\.wslconfig):
# [wsl2]
# memory=12GB
# processors=8
# gpuSupport=true
```

### Dataset too small after generation
```bash
# Use a real LLM provider for much richer examples
# 1. Get OpenAI API key: https://platform.openai.com
# 2. Set in .env: OPENAI_API_KEY=sk-...
# 3. Regenerate:
python3 scripts/generate_sft_examples.py --provider openai --limit 500

# Or use local Ollama (free, private):
# Install Ollama: https://ollama.ai
ollama pull mistral
python3 scripts/generate_sft_examples.py --provider local --limit 500
```

### Training is too slow
The RTX 2060 Super training speed for a 1B model at seq_len 512:
- LoRA (8-bit): ~10-20 steps/minute
- QLoRA (4-bit): ~15-25 steps/minute
- Expected total: 1-3 hours for 1000 examples × 3 epochs

This is normal. Reduce `num_epochs: 1` in the Axolotl config for a faster first test.
