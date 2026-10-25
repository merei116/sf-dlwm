"""Unified method interface used by the experiment runner.

Each method exposes:
    embed(img, payload, key)              -> watermarked image
    verify(attacked, registered_shape, payload, key) -> dict of metrics
The verifier's inputs model the registry-assisted setting: it knows the key,
the registered image size, and the registered ContentID fingerprint. It never
sees the attacked-vs-expected correspondence during extraction (extraction is
blind; the expected payload is used only for the final registry comparison).
"""
import time
import numpy as np

from . import robust_wm, semifragile, baseline_ll01, phash_baseline
from .robust_wm import RobustConfig
from .semifragile import AuthConfig


def _timed(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, time.perf_counter() - t0


class ProposedMethod:
    """SF-DLWM: robust pilot-synchronized ContentID layer + semi-fragile
    QIM authentication layer."""
    name = "sf_dlwm"

    def __init__(self, robust_cfg: RobustConfig = None, auth_cfg: AuthConfig = None,
                 use_auth_layer=True):
        self.rc = robust_cfg or RobustConfig()
        self.ac = auth_cfg or AuthConfig()
        self.use_auth_layer = use_auth_layer

    def embed(self, img, payload, key):
        out, t_r = _timed(robust_wm.embed, img, payload, key, self.rc)
        t_a = 0.0
        if self.use_auth_layer:
            out, t_a = _timed(semifragile.embed, out, key, self.ac)
        return out, {"t_embed_robust": t_r, "t_embed_auth": t_a}

    def verify(self, attacked, registered_shape, payload, key):
        ext, t_x = _timed(robust_wm.extract, attacked, registered_shape, key, self.rc)
        reg = robust_wm.verify_against_registry(ext, payload, self.rc)
        row = {"watermark_detected": int(reg["detected"]),
               "watermark_ber": reg["ber"], "watermark_nc": reg["nc"],
               "pilot_ber": ext["pilot_ber"], "sync_candidate": ext["sync_candidate"],
               "t_extract_robust": t_x}
        if self.use_auth_layer:
            auth, t_v = _timed(semifragile.verify, attacked, key, self.ac)
        else:
            auth = {"status": "unverifiable", "tamper_map":
                    np.zeros(attacked.shape[:2], np.uint8),
                    "median_rho": float("nan"), "flagged_ratio": 0.0}
            t_v = 0.0
        row.update({"auth_status": auth["status"],
                    "auth_median_rho": auth["median_rho"],
                    "auth_flagged_ratio": auth["flagged_ratio"],
                    "t_verify_auth": t_v})
        return row, auth["tamper_map"]


class BaselineLL01:
    name = "ll01_style_baseline"

    def __init__(self, sync_cfg: RobustConfig = None, n_bits=64):
        self.sync_cfg = sync_cfg or RobustConfig()
        self.n_bits = n_bits

    def embed(self, img, payload, key):
        out, t_r = _timed(baseline_ll01.embed_robust, img, payload, key)
        out, t_a = _timed(baseline_ll01.embed_fragile, out, key)
        return out, {"t_embed_robust": t_r, "t_embed_auth": t_a}

    def verify(self, attacked, registered_shape, payload, key):
        ext, t_x = _timed(baseline_ll01.extract_robust, attacked,
                          registered_shape, len(payload), key, self.sync_cfg)
        bits = ext["bits"]
        exp = np.asarray(payload, np.uint8)
        ber = float(np.mean(bits[:len(exp)] != exp[:len(bits)]))
        a = 2.0 * bits.astype(np.float64) - 1
        b = 2.0 * exp.astype(np.float64) - 1
        n = min(len(a), len(b))
        nc = float(np.dot(a[:n], b[:n]) / (np.linalg.norm(a[:n]) * np.linalg.norm(b[:n]) + 1e-12))
        row = {"watermark_detected": int(ber <= 0.20),
               "watermark_ber": ber, "watermark_nc": nc,
               "pilot_ber": float("nan"), "sync_candidate": ext["sync_candidate"],
               "t_extract_robust": t_x}
        auth, t_v = _timed(baseline_ll01.verify_fragile, attacked, key)
        row.update({"auth_status": auth["status"],
                    "auth_median_rho": auth["median_rho"],
                    "auth_flagged_ratio": auth["flagged_ratio"],
                    "t_verify_auth": t_v})
        return row, auth["tamper_map"]


class PHashBaseline:
    """Identification-only baseline: no embedding, no localization."""
    name = "phash_baseline"

    def __init__(self, threshold_bits=10):
        self.threshold_bits = threshold_bits

    def embed(self, img, payload, key):
        return img.copy(), {"t_embed_robust": 0.0, "t_embed_auth": 0.0}

    def verify(self, attacked, registered_shape, payload, key,
               registered_hash=None):
        t0 = time.perf_counter()
        res = phash_baseline.identify(attacked, registered_hash,
                                      self.threshold_bits)
        t = time.perf_counter() - t0
        row = {"watermark_detected": int(res["detected"]),
               "watermark_ber": res["ber"], "watermark_nc": float("nan"),
               "pilot_ber": float("nan"), "sync_candidate": "n/a",
               "t_extract_robust": t,
               "auth_status": "unverifiable", "auth_median_rho": float("nan"),
               "auth_flagged_ratio": 0.0, "t_verify_auth": 0.0}
        return row, np.zeros(attacked.shape[:2], np.uint8)
