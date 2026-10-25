"""Sensitivity sweeps.

  payload   : L in {32, 64, 128}     -> BER / detection vs. payload length
  threshold : tau_f in 0.05..0.50    -> benign FPR vs. tamper recall (auth layer)
              tau_r in 0.05..0.35    -> detection vs. analytic false alarm
  strength  : robust strength x auth QIM step -> PSNR/SSIM vs. robustness

Usage:
    python -m experiments.run_sweeps --config config.yaml --sweep payload
"""
import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config, robust_config, auth_config
from src.io_utils import resolve_dataset, read_image_rgb, ensure_dir
from src.transforms import apply_transform
from src import metrics as M
from src.keys import content_id_to_bits
from src import robust_wm, semifragile

SWEEP_SCENARIOS = ["jpeg85", "jpeg50", "resize075", "crop_center",
                   "copy_move", "inpaint_like"]


def _load(cfg, n_images):
    paths, name = resolve_dataset(cfg)
    return [(p, read_image_rgb(p, cfg["dataset"]["image_size"]))
            for p in paths[:n_images]], name


def sweep_payload(cfg, n_images):
    rows = []
    images, _ = _load(cfg, n_images)
    for L in (32, 64, 128):
        rc = robust_config(cfg)
        rc.payload_bits = L
        for path, img in images:
            payload = content_id_to_bits(f"cid::{path.name}", L)
            wm = robust_wm.embed(img, payload, cfg["key"], rc)
            for scen in ["jpeg85", "jpeg50", "resize075", "crop_center",
                         "whatsapp_like", "mixed_instagram_crop_jpeg"]:
                attacked, _ = apply_transform(scen, wm, seed=cfg["seed"])
                ext = robust_wm.extract(attacked, img.shape, cfg["key"], rc)
                reg = robust_wm.verify_against_registry(ext, payload, rc)
                rows.append({"payload_bits": L, "scenario": scen,
                             "image": path.name, "ber": reg["ber"],
                             "nc": reg["nc"], "detected": int(reg["detected"]),
                             "pilot_ber": ext["pilot_ber"],
                             "psnr_wm": M.psnr(img, wm)})
    return pd.DataFrame(rows)


def sweep_threshold(cfg, n_images):
    """Vary tau_f post-hoc on stored mismatch maps (cheap and exact)."""
    rows = []
    images, _ = _load(cfg, n_images)
    ac = auth_config(cfg)
    rc = robust_config(cfg)
    for path, img in images:
        payload = content_id_to_bits(f"cid::{path.name}", rc.payload_bits)
        wm = semifragile.embed(robust_wm.embed(img, payload, cfg["key"], rc),
                               cfg["key"], ac)
        for scen in ["jpeg85", "jpeg70", "noise8", "copy_move", "inpaint_like"]:
            attacked, gt = apply_transform(scen, wm, seed=cfg["seed"])
            rho = semifragile._mismatch_map(attacked, cfg["key"], ac)
            for tau in np.arange(0.05, 0.55, 0.05):
                a = copy.deepcopy(ac)
                a.tau_f = float(tau)
                flagged = semifragile._cleanup(rho >= tau, a)
                up = np.kron(flagged, np.ones((16, 16), bool))
                up = up[:attacked.shape[0], :attacked.shape[1]]
                row = {"tau_f": float(tau), "scenario": scen, "image": path.name,
                       "median_rho": float(np.median(rho))}
                if gt is not None:
                    gtc = gt[:up.shape[0], :up.shape[1]] > 0
                    row.update(M.mask_metrics(up, gtc))
                else:
                    row["benign_fpr"] = float(up.mean())
                rows.append(row)
    return pd.DataFrame(rows)


def sweep_strength(cfg, n_images):
    rows = []
    images, _ = _load(cfg, n_images)
    for strength in (22.0, 28.0, 34.0, 40.0):
        for delta in (18.0, 26.0, 34.0):
            rc = robust_config(cfg)
            rc.strength = strength
            ac = auth_config(cfg)
            ac.delta = delta
            for path, img in images:
                payload = content_id_to_bits(f"cid::{path.name}", rc.payload_bits)
                wm = semifragile.embed(
                    robust_wm.embed(img, payload, cfg["key"], rc), cfg["key"], ac)
                psnr, ssim = M.psnr(img, wm), M.ssim_rgb(img, wm)
                for scen in ["jpeg70", "jpeg50", "whatsapp_like"]:
                    attacked, _ = apply_transform(scen, wm, seed=cfg["seed"])
                    ext = robust_wm.extract(attacked, img.shape, cfg["key"], rc)
                    reg = robust_wm.verify_against_registry(ext, payload, rc)
                    auth = semifragile.verify(attacked, cfg["key"], ac)
                    rows.append({"strength": strength, "delta": delta,
                                 "scenario": scen, "image": path.name,
                                 "psnr_wm": psnr, "ssim_wm": ssim,
                                 "ber": reg["ber"], "detected": int(reg["detected"]),
                                 "auth_status": auth["status"],
                                 "auth_fpr": auth["flagged_ratio"]})
    return pd.DataFrame(rows)


SWEEPS = {"payload": sweep_payload, "threshold": sweep_threshold,
          "strength": sweep_strength}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--sweep", choices=SWEEPS, required=True)
    ap.add_argument("--n-images", type=int, default=8)
    args = ap.parse_args()
    cfg = load_config(args.config)
    df = SWEEPS[args.sweep](cfg, args.n_images)
    out = Path(cfg["output"]["results_dir"])
    ensure_dir(out)
    df.to_csv(out / f"sweep_{args.sweep}.csv", index=False)
    print(df.groupby([c for c in df.columns if c in
                      ("payload_bits", "tau_f", "strength", "delta", "scenario")][:2])
          .mean(numeric_only=True).round(4).head(30))
