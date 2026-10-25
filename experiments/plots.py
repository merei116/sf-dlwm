"""Generate the paper figures from raw metric CSVs.

Usage:
    python -m experiments.plots --results results/ --figures figures/
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def ensure(p):
    Path(p).mkdir(parents=True, exist_ok=True)


def grouped_bar(df, x, y, hue, title, ylabel, out):
    piv = df.pivot_table(index=x, columns=hue, values=y, aggfunc="mean")
    ax = piv.plot(kind="bar", figsize=(13, 5))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out, dpi=220)
    plt.close()


def line_sweep(df, x, y, hue, title, ylabel, out):
    piv = df.pivot_table(index=x, columns=hue, values=y, aggfunc="mean")
    ax = piv.plot(marker="o", figsize=(8, 5))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(out, dpi=220)
    plt.close()


def main(results, figures):
    ensure(figures)
    res, fig = Path(results), Path(figures)
    df = pd.read_csv(res / "benchmark_metrics.csv")
    benign, tamper = df[df.has_gt == 0], df[df.has_gt == 1]

    grouped_bar(benign, "scenario", "watermark_detected", "method",
                "Robust watermark detection rate (benign scenarios)",
                "Detection rate", fig / "fig_detection_rate.png")
    grouped_bar(benign, "scenario", "watermark_ber", "method",
                "Robust payload BER (benign scenarios)", "Mean BER",
                fig / "fig_ber.png")
    grouped_bar(benign, "scenario", "benign_fpr", "method",
                "Authentication-layer false positive rate (benign scenarios)",
                "Flagged pixel fraction", fig / "fig_auth_fpr.png")
    if len(tamper):
        grouped_bar(tamper, "scenario", "tamper_iou", "method",
                    "Tamper localization IoU", "IoU", fig / "fig_iou.png")
        grouped_bar(tamper, "scenario", "tamper_f1", "method",
                    "Tamper localization F1 / Dice", "F1",
                    fig / "fig_f1.png")

    # availability of the auth layer per scenario (tri-state honesty plot)
    av = benign.assign(available=(benign.auth_status != "unverifiable")
                       .astype(float))
    grouped_bar(av, "scenario", "available", "method",
                "Authentication availability (verifiable fraction)",
                "Fraction verifiable", fig / "fig_auth_availability.png")

    for name, xcol, ycols in [
            ("sweep_payload", "payload_bits", ["ber", "detected"]),
            ("sweep_threshold", "tau_f", ["benign_fpr", "tamper_recall",
                                          "tamper_iou"]),
            ("sweep_strength", "strength", ["psnr_wm", "ber"])]:
        p = res / f"{name}.csv"
        if p.exists():
            sw = pd.read_csv(p)
            for y in ycols:
                if y in sw.columns:
                    line_sweep(sw, xcol, y, "scenario",
                               f"{name}: {y} vs {xcol}", y,
                               fig / f"fig_{name}_{y}.png")

    ab = res / "ablation.csv"
    if ab.exists():
        adf = pd.read_csv(ab)
        grouped_bar(adf, "scenario", "watermark_detected", "variant",
                    "Ablation: detection rate", "Detection rate",
                    fig / "fig_ablation_detection.png")
        td = adf[adf.scenario.isin(["copy_move", "inpaint_like"])]
        if len(td) and "tamper_iou" in td.columns:
            grouped_bar(td, "scenario", "tamper_iou", "variant",
                        "Ablation: localization IoU", "IoU",
                        fig / "fig_ablation_iou.png")
    print(f"figures written to {fig}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--figures", default="figures")
    a = ap.parse_args()
    main(a.results, a.figures)
