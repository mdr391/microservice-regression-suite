"""YAML config loading with environment variable expansion."""
from __future__ import annotations

import os
from typing import Any

import yaml


def load_config(config_path: str) -> dict[str, Any]:
    """Load YAML config, expanding ${ENV_VAR} references."""
    with open(config_path) as f:
        raw = f.read()

    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)

    return yaml.safe_load(raw)
