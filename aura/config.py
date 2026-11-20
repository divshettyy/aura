"""Configuration: built-in defaults merged with the user's config.yaml."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import yaml

IS_WINDOWS = sys.platform == "win32"


def data_dir() -> Path:
    override = os.environ.get("AURA_HOME")
    if override:
        base = Path(override)
    elif IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home())) / "Aura"
    else:
        base = Path.home() / ".config" / "aura"
    base.mkdir(parents=True, exist_ok=True)
    return base


DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_config.yaml"


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def user_config_path() -> Path:
    return data_dir() / "config.yaml"


def load() -> dict:
    """Defaults, overlaid with the user's file. A broken user file is an error, not ignored."""
    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    path = user_config_path()
    if path.exists():
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(user, dict):
            raise ValueError(f"{path} must contain a YAML mapping")
        cfg = _merge(cfg, user)
    return cfg


def expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))
