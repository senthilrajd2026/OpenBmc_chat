.PHONY: help setup check clone fetch-issues parse generate validate split train infer eval-dataset eval-model clean

PYTHON := python3
SCRIPTS := scripts
SRC := src

help:
	@echo ""
	@echo "openbmc-ft-poc - OpenBMC fine-tuning pipeline"
	@echo "================================================"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Install Python dependencies"
	@echo "  make check          Detect environment capabilities"
	@echo ""
	@echo "Data pipeline:"
	@echo "  make clone          Clone OpenBMC source repos"
	@echo "  make fetch-issues   Fetch GitHub issues"
	@echo "  make parse          Parse docs, services, D-Bus strings"
	@echo "  make generate       Generate SFT examples"
	@echo "  make validate       Validate and deduplicate"
	@echo "  make split          Split into train/eval"
	@echo ""
	@echo "Build (optional):"
	@echo "  make build-check    Run OpenBMC build precheck"
	@echo "  make build-dry      Run build in dry-run mode"
	@echo ""
	@echo "Training:"
	@echo "  make train-lora     Fine-tune with LoRA"
	@echo "  make train-qlora    Fine-tune with QLoRA"
	@echo "  make infer          Run inference on fine-tuned model"
	@echo ""
	@echo "Evaluation:"
	@echo "  make eval-dataset   Evaluate dataset quality"
	@echo "  make eval-model     Evaluate model quality"
	@echo ""
	@echo "Utilities:"
	@echo "  make pipeline       Run full data pipeline (no training)"
	@echo "  make clean          Remove generated data"
	@echo ""

setup:
	pip install -r requirements.txt
	pip install -e .

check:
	$(PYTHON) $(SCRIPTS)/check_env.py

clone:
	$(PYTHON) $(SCRIPTS)/clone_sources.py

fetch-issues:
	$(PYTHON) $(SCRIPTS)/fetch_github_issues.py

parse:
	$(PYTHON) $(SCRIPTS)/parse_docs.py
	$(PYTHON) $(SCRIPTS)/parse_repo_metadata.py
	$(PYTHON) $(SCRIPTS)/parse_services.py
	$(PYTHON) $(SCRIPTS)/parse_dbus_strings.py
	$(PYTHON) $(SCRIPTS)/parse_logs_and_errors.py
	$(PYTHON) $(SCRIPTS)/chunk_sources.py

generate:
	$(PYTHON) $(SCRIPTS)/generate_sft_examples.py

validate:
	$(PYTHON) $(SCRIPTS)/validate_examples.py
	$(PYTHON) $(SCRIPTS)/dedupe_examples.py

split:
	$(PYTHON) $(SCRIPTS)/split_dataset.py

build-check:
	bash $(SCRIPTS)/build_openbmc_if_requested.sh --check-only

build-dry:
	bash $(SCRIPTS)/build_openbmc_if_requested.sh --dry-run

train-lora:
	bash $(SCRIPTS)/train.sh lora

train-qlora:
	bash $(SCRIPTS)/train.sh qlora

infer:
	bash $(SCRIPTS)/infer.sh

eval-dataset:
	$(PYTHON) $(SCRIPTS)/evaluate_dataset.py

eval-model:
	$(PYTHON) $(SCRIPTS)/evaluate_model.py

# Full data pipeline (no training or build)
pipeline: clone fetch-issues parse generate validate split eval-dataset

clean:
	@echo "Removing generated intermediate and processed data..."
	rm -rf data/intermediate/* data/processed/* data/reports/*
	rm -f data/train.jsonl data/eval.jsonl
	@echo "Done. Raw data and repos preserved."

clean-all: clean
	@echo "Removing raw downloaded repos..."
	rm -rf data/raw/*
	@echo "Done."

test:
	pytest tests/ -v --cov=src/openbmc_ft_poc --cov-report=term-missing
