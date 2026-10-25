"""Config loading: YAML -> dataclasses, with reproducibility metadata."""
import copy
import yaml
from pathlib import Path

from .robust_wm import RobustConfig
from .semifragile import AuthConfig

DEFAULTS = {
    "seed": 42,
    "key": "sfdlwm-benchmark-key-2026",
    "dataset": {"image_dir": "data/images", "demo_dir": "data/demo",
                "n_images": 39, "image_size": 512},
    "robust": {}, "auth": {},
    "output": {"results_dir": "results", "figures_dir": "figures"},
    "scenarios": None,   # None -> all
    "methods": ["sf_dlwm", "ll01_style_baseline", "phash_baseline"],
}


def load_config(path):
    cfg = copy.deepcopy(DEFAULTS)
    if path and Path(path).exists():
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def robust_config(cfg):
    d = {k: v for k, v in cfg.get("robust", {}).items()}
    for key in ("crop_ratios", "sync_rotations", "sync_crop_ratios"):
        if key in d:
            d[key] = tuple(d[key])
    return RobustConfig(**d)


def auth_config(cfg):
    return AuthConfig(**cfg.get("auth", {}))
