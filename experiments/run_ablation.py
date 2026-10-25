"""Ablation study on the proposed method.

Variants:
  full                 : complete SF-DLWM
  no_pilot_sync        : sync candidates ranked by soft confidence, not pilots
  no_ecc               : ecc_rate = 1 (redundancy budget held constant by
                         raising carrier repeats accordingly)
  no_stream_b          : full-frame stream only (no crop anchoring)
  no_coord_binding     : auth code not XORed with the position mask
  no_auth_layer        : robust layer alone (interaction check: does the auth
                         layer degrade robust recovery?)

Usage:
    python -m experiments.run_ablation --config config.yaml --n-images 10
"""
import argparse
import copy
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config, robust_config, auth_config
from src.io_utils import resolve_dataset, read_image_rgb, ensure_dir
from src.transforms import apply_transform
from src import metrics as M
from src.keys import content_id_to_bits
from src.pipeline import ProposedMethod

SCENARIOS = ["jpeg50", "resize075", "crop_center", "rotate5",
             "mixed_instagram_crop_jpeg", "copy_move", "inpaint_like"]


def make_variants(cfg):
    rc0, ac0 = robust_config(cfg), auth_config(cfg)
    variants = {}
    variants["full"] = ProposedMethod(copy.deepcopy(rc0), copy.deepcopy(ac0))
    rc = copy.deepcopy(rc0); rc.use_pilot_sync = False
    variants["no_pilot_sync"] = ProposedMethod(rc, copy.deepcopy(ac0))
    rc = copy.deepcopy(rc0)
    rc.repeats_a *= rc.ecc_rate; rc.repeats_b *= rc.ecc_rate; rc.ecc_rate = 1
    variants["no_ecc"] = ProposedMethod(rc, copy.deepcopy(ac0))
    rc = copy.deepcopy(rc0); rc.use_stream_b = False
    variants["no_stream_b"] = ProposedMethod(rc, copy.deepcopy(ac0))
    ac = copy.deepcopy(ac0); ac.coordinate_binding = False
    variants["no_coord_binding"] = ProposedMethod(copy.deepcopy(rc0), ac)
    variants["no_auth_layer"] = ProposedMethod(copy.deepcopy(rc0),
                                               copy.deepcopy(ac0),
                                               use_auth_layer=False)
    return variants


def run(cfg, n_images):
    paths, _ = resolve_dataset(cfg)
    rows = []
    for path in paths[:n_images]:
        img = read_image_rgb(path, cfg["dataset"]["image_size"])
        payload = content_id_to_bits(f"cid::{path.name}",
                                     robust_config(cfg).payload_bits)
        for vname, method in make_variants(cfg).items():
            wm, _ = method.embed(img, payload, cfg["key"])
            psnr = M.psnr(img, wm)
            for scen in SCENARIOS:
                attacked, gt = apply_transform(scen, wm, seed=cfg["seed"])
                row, tmap = method.verify(attacked, img.shape, payload, cfg["key"])
                row.update({"variant": vname, "scenario": scen,
                            "image": path.name, "psnr_wm": psnr})
                if gt is not None:
                    row.update(M.mask_metrics(tmap > 0, gt > 0))
                else:
                    row["benign_fpr"] = float((tmap > 0).mean())
                rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--n-images", type=int, default=10)
    args = ap.parse_args()
    cfg = load_config(args.config)
    df = run(cfg, args.n_images)
    out = Path(cfg["output"]["results_dir"])
    ensure_dir(out)
    df.to_csv(out / "ablation.csv", index=False)
    print(df.groupby(["variant", "scenario"])[
        ["watermark_detected", "watermark_ber"]].mean().round(3))
