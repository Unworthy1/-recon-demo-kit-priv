"""Build adapters from the deployment config (derived from INTAKE.md).

Adapters that need a code callable (e.g. a watched-folder parser) are wired by the agent in
`wiring.py` and referenced by name; everything else comes from config.example.yaml.
"""
from __future__ import annotations

import os

import yaml

# importing the modules registers their adapters via @register(...)
import adapters.gl        # noqa: F401
import adapters.treasury  # noqa: F401
import adapters.dms       # noqa: F401
from adapters.base import get_adapter


def load() -> dict:
    with open(os.environ.get("CONFIG_PATH", "/config/config.yaml")) as f:
        return yaml.safe_load(f)


def build_gl(cfg: dict):
    g = cfg["gl"]
    return get_adapter("gl", g["adapter"])(**g.get("args", {}))


def build_treasury(cfg: dict) -> list:
    out = []
    for s in cfg.get("treasury", []):
        out.append(get_adapter("treasury", s["adapter"])(**s.get("args", {})))
    return out


def build_dms(cfg: dict):
    d = cfg.get("dms")
    return get_adapter("dms", d["adapter"])(**d.get("args", {})) if d else None
