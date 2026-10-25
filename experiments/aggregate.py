"""Aggregate raw metric CSVs into the paper's tables (CSV + Markdown).

Usage:
    python -m experiments.aggregate --results results/
"""
import argparse
from pathlib import Path
import pandas as pd


def _save(df, out_dir, name):
    df.to_csv(out_dir / f"{name}.csv")
    (out_dir / f"{name}.md").write_text(df.round(4).to_markdown())
    print(f"table: {name}\n{df.round(3)}\n")


def main(results_dir):
    out = Path(results_dir)
    df = pd.read_csv(out / "benchmark_metrics.csv")

    benign = df[df.has_gt == 0]
    tamper = df[df.has_gt == 1]

    # Table 1: robust recovery per method x scenario
    t1 = benign.pivot_table(index="scenario", columns="method",
                            values=["watermark_detected", "watermark_ber"],
                            aggfunc="mean")
    _save(t1, out, "table_robust_by_scenario")

    # Table 2: overall comparison
    overall = df.groupby("method").agg(
        detection_rate=("watermark_detected", "mean"),
        mean_ber=("watermark_ber", "mean"),
        mean_nc=("watermark_nc", "mean"),
        psnr=("psnr_wm", "mean"), ssim=("ssim_wm", "mean"),
        t_extract_s=("t_extract_robust", "mean"))
    _save(overall, out, "table_overall")

    # Table 3: auth layer on benign scenarios (availability + FPR)
    ben = benign.assign(verifiable=(benign.auth_status != "unverifiable")
                        .astype(float))
    t3 = ben.groupby(["method", "scenario"]).agg(
        auth_available=("verifiable", "mean"),
        benign_fpr=("benign_fpr", "mean")).unstack(0)
    _save(t3, out, "table_auth_benign")

    # Table 4: localization on tamper scenarios
    t4 = tamper.groupby(["method", "scenario"]).agg(
        precision=("tamper_precision", "mean"),
        recall=("tamper_recall", "mean"),
        f1=("tamper_f1", "mean"), iou=("tamper_iou", "mean"),
        fpr=("tamper_fpr", "mean"))
    t4_std = tamper.groupby(["method", "scenario"])[["tamper_iou"]].std() \
        .rename(columns={"tamper_iou": "iou_std"})
    _save(t4.join(t4_std), out, "table_localization")

    # Table 5: negative controls
    neg_path = out / "benchmark_negative_controls.csv"
    if neg_path.exists():
        neg = pd.read_csv(neg_path)
        t5 = neg.groupby(["method", "control"]).agg(
            false_detection_rate=("watermark_detected", "mean"),
            mean_ber=("watermark_ber", "mean"),
            mean_pilot_ber=("pilot_ber", "mean"))
        _save(t5, out, "table_negative_controls")

    # Table 6: runtime
    t6 = df.groupby("method")[["t_embed_robust", "t_embed_auth",
                               "t_extract_robust", "t_verify_auth"]].mean()
    _save(t6, out, "table_runtime")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    main(ap.parse_args().results)
