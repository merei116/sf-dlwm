# SF-DLWM: Semi-Fragile Dual-Layer Watermarking for Provenance Verification and Localized Tamper Detection

Reference implementation and benchmark for the paper
*"SF-DLWM: A Reproducible Dual-Layer Watermarking Framework Combining
Pilot-Synchronized Robust Provenance Recovery with Semi-Fragile Tamper
Localization"* (see `paper/PAPER.md`).

## What this is

Two independent, key-driven watermark layers embedded in one pipeline:

1. **Layer R (robust ContentID)** — differential DCT modulation with a
   repetition-coded 64-bit payload, key-derived **pilot bits** for blind
   geometric synchronization and presence testing, and a crop-anchored
   second carrier stream. Detection is a hypothesis test with an analytic
   false-alarm bound plus empirical negative controls (wrong key,
   unwatermarked images).
2. **Layer A (semi-fragile authentication)** — per-16×16-block, Gray-coded
   quantized luminance features, XORed with a key/position mask (exposes
   copy-move), embedded by QIM in mid-frequency DCT coefficients so the
   layer **survives mild JPEG** (tolerance class set by the QIM step) while
   local edits are detected and localized. Verification is **tri-state**:
   `authentic` / `tampered` (with a map) / `unverifiable`.

There is deliberately **no hidden pixel-statistics anomaly detector**: every
localization decision is traceable to the watermark, and every extraction is
blind (the expected payload is used only for the final registry comparison,
never inside the decoder).

## Layout

```
config.yaml            single source of truth for all parameters
src/                   library (keys, ecc, robust_wm, semifragile,
                       baselines, transforms, metrics, pipeline)
experiments/           run_benchmark, run_sweeps, run_ablation,
                       aggregate, plots
scripts/run_all.sh     regenerates every table and figure
paper/PAPER.md         the paper
data/images/           put the evaluation dataset here (see below)
results/, figures/     generated outputs
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Dataset

Place real evaluation images in `data/images/` — e.g., the USC-SIPI
miscellaneous volume:

```bash
# https://sipi.usc.edu/database/  (misc volume); convert to PNG into data/images/
```

If `data/images/` is empty, a **deterministic synthetic fallback** is
generated in `data/demo/` and every result row is labeled
`dataset=synthetic_demo`, so results can never be silently misattributed
to a real dataset.

## Reproduce everything

```bash
bash scripts/run_all.sh
```

or step by step:

```bash
python -m experiments.run_benchmark --config config.yaml --tag benchmark
python -m experiments.run_sweeps    --config config.yaml --sweep payload   --n-images 10
python -m experiments.run_sweeps    --config config.yaml --sweep threshold --n-images 10
python -m experiments.run_sweeps    --config config.yaml --sweep strength  --n-images 6
python -m experiments.run_ablation  --config config.yaml --n-images 10
python -m experiments.aggregate     --results results
python -m experiments.plots         --results results --figures figures
```

Outputs: `results/benchmark_metrics.csv` (one row per image × method ×
scenario, all metrics), `results/benchmark_negative_controls.csv`,
`results/table_*.{csv,md}` (paper tables), `figures/*.png` (paper figures),
`results/benchmark_manifest.json` (dataset name, seed, key fingerprint,
scenario list, analytic false-alarm probability, wall time).

Reproducibility controls: fixed `seed` and `key` in `config.yaml`; all
randomness derived via keyed BLAKE2s PRFs; the manifest records the exact
run configuration.

## Smoke-test results (synthetic fallback, 3 images — for validation only)

| | detection rate | mean BER | benign auth FPR | copy-move IoU | inpaint IoU |
|---|---|---|---|---|---|
| SF-DLWM | 1.000 | 0.000 | ≤0.014 | 0.81 | 0.87 |
| LL01-style (fair sync) | 0.762 | 0.123 | ~0.50 under JPEG | 0.47 | 0.10 |
| pHash | 0.841 | — | — | — | — |

Negative controls: wrong-key and unwatermarked false-detection rate 0.000
(analytic random-payload false-alarm at τ_r = 0.20, L = 64: 2.3 × 10⁻⁷).
Paper-grade numbers must be produced on a real dataset via
`scripts/run_all.sh`.

## Notes on fairness

The LL01-style baseline receives the **same** geometric synchronization
candidate set as the proposed method (ranked by its own confidence). No
method ever receives the expected payload during extraction. This corrects
two flaws of the original benchmark (oracle-assisted synchronization for the
proposed method only; no synchronization for the baseline).
