"""
Configuration loader for openbmc-ft-poc.

Loads settings.yaml, sources.yaml, and dataset_rules.yaml.
Merges environment variable overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Project root is two levels up from this file:
# src/openbmc_ft_poc/config.py → parents[0]=src/openbmc_ft_poc, parents[1]=src, parents[2]=project_root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Config:
    """
    Central configuration object.

    Merges YAML configs with .env overrides.
    All path resolution is relative to project root.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)

        self._config_dir = config_dir or CONFIGS_DIR
        self.settings: dict[str, Any] = _load_yaml(self._config_dir / "settings.yaml")
        self.sources: dict[str, Any] = _load_yaml(self._config_dir / "sources.yaml")
        self.dataset_rules: dict[str, Any] = _load_yaml(
            self._config_dir / "dataset_rules.yaml"
        )

        # Apply env overrides
        self._apply_env_overrides()

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_raw(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["data_raw"]

    @property
    def data_intermediate(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["data_intermediate"]

    @property
    def data_processed(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["data_processed"]

    @property
    def data_reports(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["data_reports"]

    @property
    def data_logs(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["data_logs"]

    @property
    def train_output(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["train_output"]

    @property
    def eval_output(self) -> Path:
        return PROJECT_ROOT / self.settings["paths"]["eval_output"]

    @property
    def llm_provider(self) -> str:
        return os.environ.get("LLM_PROVIDER", self.settings["llm"]["provider"])

    @property
    def github_token(self) -> str | None:
        return os.environ.get("GITHUB_TOKEN")

    @property
    def log_level(self) -> str:
        return os.environ.get(
            "LOG_LEVEL", self.settings.get("logging", {}).get("level", "INFO")
        )

    @property
    def seed(self) -> int:
        return self.settings["dataset"]["seed"]

    @property
    def debug_patterns(self) -> list[dict[str, Any]]:
        return self.dataset_rules.get("debug_patterns", [])

    @property
    def subsystems(self) -> list[dict[str, Any]]:
        return self.dataset_rules.get("subsystems", [])

    @property
    def repos(self) -> list[dict[str, Any]]:
        return [r for r in self.sources.get("repos", []) if r.get("enabled", True)]

    @property
    def issue_sources(self) -> list[dict[str, Any]]:
        return [s for s in self.sources.get("issues", []) if s.get("enabled", True)]

    def ensure_dirs(self) -> None:
        """Create all data directories if they don't exist."""
        for d in [
            self.data_raw,
            self.data_intermediate,
            self.data_processed,
            self.data_reports,
            self.data_logs,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def _apply_env_overrides(self) -> None:
        """Override config values from environment variables."""
        # Allow overriding data directories
        for key, attr in [
            ("DATA_RAW_DIR", ("paths", "data_raw")),
            ("DATA_INTERMEDIATE_DIR", ("paths", "data_intermediate")),
            ("DATA_PROCESSED_DIR", ("paths", "data_processed")),
        ]:
            val = os.environ.get(key)
            if val:
                self.settings[attr[0]][attr[1]] = val


# Module-level singleton
_config: Config | None = None


def get_config(config_dir: Path | None = None) -> Config:
    """Return the singleton Config instance."""
    global _config
    if _config is None:
        _config = Config(config_dir=config_dir)
    return _config


def reset_config() -> None:
    """Reset singleton (useful in tests)."""
    global _config
    _config = None
