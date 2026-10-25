"""Main benchmark.

For every (image, method): embed once, measure embedding quality (PSNR/SSIM),
then for every scenario: attack, verify blindly, log all metrics. Also runs
the negative controls required for an honest detection claim:
  * wrong-key extraction on watermarked images,
  * extraction from unwatermarked images.

Usage:
    python -m experiments.run_benchmark --config config.yaml [--n-images N]
        [--scenarios s1,s2] [--tag NAME]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config, robust_config, auth_config
from src.io_utils import resolve_dataset, read_image_rgb, save_image_rgb, ensure_dir
from src.transforms import apply_transform, ALL_SCENARIOS, TAMPER
from src import metrics as M
from src.keys import content_id_to_bits
from src.pipeline import ProposedMethod, BaselineLL01, PHashBaseline
from src.phash_baseline import phash


def build_methods(cfg):
    rc, ac = robust_config(cfg), auth_config(cfg)
    table = {
        "sf_dlwm": lambda: ProposedMethod(rc, ac),
        "ll01_style_baseline": lambda: BaselineLL01(rc, n_bits=rc.payload_bits),
        "phash_baseline": lambda: PHashBaseline(),
    }
    return [table[m]() for m in cfg["methods"]]


def run(cfg, n_images=None, scenarios=None, tag="benchmark", save_examples=True):
    rc = robust_config(cfg)
    out_dir = Path(cfg["output"]["results_dir"])
    ensure_dir(out_dir)
    paths, dataset_name = resolve_dataset(cfg)
    if n_images:
        paths = paths[:n_images]
    scenarios = scenarios or cfg["scenarios"] or ALL_SCENARIOS
    methods = build_methods(cfg)
    key, wrong_key = cfg["key"], cfg["key"] + "-WRONG"
    size = cfg["dataset"]["image_size"]

    rows, neg_rows = [], []
    t_start = time.time()
    for ip, path in enumerate(paths):
        original = read_image_rgb(path, size)
        content_id = f"cid::{dataset_name}::{path.name}"
        payload = content_id_to_bits(content_id, rc.payload_bits)
        reg_hash = phash(original)
        for method in methods:
            wm, t_embed = method.embed(original, payload, key)
            q_psnr = M.psnr(original, wm)
            q_ssim = M.ssim_rgb(original, wm)
            for scen in scenarios:
                attacked, gt = apply_transform(scen, wm, seed=cfg["seed"] + ip)
                kwargs = {"registered_hash": reg_hash} \
                    if isinstance(method, PHashBaseline) else {}
                row, tamper_map = method.verify(attacked, original.shape,
                                                payload, key, **kwargs)
                row.update({"method": method.name, "scenario": scen,
                            "image": path.name, "dataset": dataset_name,
                            "psnr_wm": q_psnr, "ssim_wm": q_ssim, **t_embed})
                if gt is not None:
                    row.update(M.mask_metrics(tamper_map > 0, gt > 0))
                    row["has_gt"] = 1
                else:
                    # benign scenario: any flagged pixel is a false positive
                    row["benign_fpr"] = float((tamper_map > 0).mean())
                    row["has_gt"] = 0
                rows.append(row)
                if save_examples and ip == 0 and scen in TAMPER \
                        and method.name == "sf_dlwm":
                    ex = Path(cfg["output"]["figures_dir"]) / "examples"
                    save_image_rgb(ex / f"{scen}_original.png", original)
                    save_image_rgb(ex / f"{scen}_watermarked.png", wm)
                    save_image_rgb(ex / f"{scen}_attacked.png", attacked)
                    save_image_rgb(ex / f"{scen}_gt.png",
                                   np.dstack([gt] * 3))
                    save_image_rgb(ex / f"{scen}_pred.png",
                                   np.dstack([tamper_map] * 3))
            # negative controls (identity channel is sufficient and cheapest)
            if method.name != "phash_baseline":
                r_wrong, _ = method.verify(wm, original.shape, payload, wrong_key)
                neg_rows.append({"method": method.name, "control": "wrong_key",
                                 "image": path.name,
                                 "watermark_detected": r_wrong["watermark_detected"],
                                 "watermark_ber": r_wrong["watermark_ber"],
                                 "pilot_ber": r_wrong["pilot_ber"]})
                r_unmarked, _ = method.verify(original, original.shape, payload, key)
                neg_rows.append({"method": method.name, "control": "unwatermarked",
                                 "image": path.name,
                                 "watermark_detected": r_unmarked["watermark_detected"],
                                 "watermark_ber": r_unmarked["watermark_ber"],
                                 "pilot_ber": r_unmarked["pilot_ber"]})
        print(f"[{ip + 1}/{len(paths)}] {path.name} done "
              f"({time.time() - t_start:.1f}s elapsed)", flush=True)

    df = pd.DataFrame(rows)
    neg = pd.DataFrame(neg_rows)
    df.to_csv(out_dir / f"{tag}_metrics.csv", index=False)
    neg.to_csv(out_dir / f"{tag}_negative_controls.csv", index=False)
    manifest = {"tag": tag, "dataset": dataset_name, "n_images": len(paths),
                "scenarios": list(scenarios), "methods": [m.name for m in methods],
                "seed": cfg["seed"], "key_fingerprint": str(hash(key) & 0xFFFFFFFF),
                "payload_bits": rc.payload_bits,
                "analytic_random_payload_fa":
                    M.random_payload_false_alarm(rc.payload_bits, rc.ber_threshold),
                "wall_time_s": time.time() - t_start}
    with open(out_dir / f"{tag}_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))
    return df, neg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--n-images", type=int, default=None)
    ap.add_argument("--scenarios", default=None)
    ap.add_argument("--tag", default="benchmark")
    args = ap.parse_args()
    cfg = load_config(args.config)
    scen = args.scenarios.split(",") if args.scenarios else None
    run(cfg, n_images=args.n_images, scenarios=scen, tag=args.tag)
