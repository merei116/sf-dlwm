# Diagnosis of the Original Paper and Code (audit record)

Each item: **problem → why it weakens the paper → exact fix (implemented here)**.

## Fatal / major

1. **Oracle-assisted extraction.** `try_extract_with_resizing(..., expected_bits=...)`
   ranked synchronization candidates by BER against the *expected payload* and
   early-exited at BER ≤ 0.01. → The reported detection rate 1.00 / BER 0.000 /
   NC 1.000 are artifacts of ground-truth leakage into the decoder; the system
   is unrealizable (a verifier steering by the expected payload has nothing
   left to verify). → **Fix:** key-derived pilot bits rank candidates
   (`src/robust_wm.py`); the expected payload is used only in the final
   registry comparison.

2. **"Average NC values above 1.000" (abstract).** NC ∈ [−1, 1] by
   Cauchy–Schwarz; the claim is mathematically impossible and signals an
   aggregation bug. → Destroys credibility of all reported numbers. →
   **Fix:** NC computed on bipolar vectors with explicit normalization
   (`src/metrics.py`); aggregation script emits the tables directly.

3. **No negative controls.** Detection was evaluated only on watermarked
   images with the correct key; the detector's false-alarm rate was never
   measured. → A detection rate without a matched false-alarm rate is not a
   detection claim. → **Fix:** wrong-key and unwatermarked controls in every
   benchmark run + analytic binomial false-alarm bound
   (`experiments/run_benchmark.py`, `metrics.random_payload_false_alarm`).

4. **Fragile LSB layer incompatible with the threat model, hidden fallback.**
   Any re-encoding randomizes LSBs (mismatch ≈ 0.5 everywhere); the code
   silently switched (ratio > 0.45) to `_smooth_anomaly`, a hand-tuned
   pixel-statistics heuristic that is not watermark-based and is not
   disclosed in the paper. The reported FPR = 0.057 and the inpainting IoU
   derive from that heuristic. → Code–paper inconsistency; the headline
   fragile-layer results do not measure the fragile layer. → **Fix:**
   semi-fragile QIM layer (`src/semifragile.py`) that tolerates a declared
   JPEG class; heuristic removed entirely; tri-state output
   (authentic/tampered/unverifiable) instead of unconditional maps.

5. **Unfair baseline.** The LL01-style baseline received no geometric
   synchronization while the proposed method used the oracle-assisted search.
   → The reported gap (1.00 vs 0.465) conflates embedding quality with an
   evaluation asymmetry; strawman comparison. → **Fix:** shared candidate set
   for all methods, each ranked by its own key-legitimate score
   (`src/baseline_ll01.py`).

6. **Dataset inconsistency.** The paper claims a 39-image USC-SIPI subset;
   the code generates 39 synthetic shape images (`generate_demo_dataset`).
   → Results are unattributable; reproduction impossible. → **Fix:** dataset
   resolution logic labels every result row with the dataset actually used;
   synthetic fallback is explicitly named `synthetic_demo`
   (`src/io_utils.resolve_dataset`, manifest JSON).

7. **Invalid inpainting attack.** `inpainting_like_attack` Gaussian-blurred
   the ENTIRE image while the GT mask covered only the patch. → The "attack"
   is a global filter; localization metrics against a local-only GT are
   ill-defined, and the fragile layer was destroyed frame-wide by the attack
   itself. → **Fix:** smoothing confined to the edited region; added
   tamper+JPEG85 scenarios (`src/transforms.py`).

## Serious

8. **Figure 2 "decision matrix" presents hand-assigned suitability scores
   (1.00, 0.97, ...) as experimental results.** → Opinion formatted as data.
   → **Fix:** removed; the comparison is carried by measured baselines
   (pHash, LL01) under the same protocol.

9. **Missing required analyses:** payload sensitivity, threshold sensitivity,
   ablation, runtime, variance/spread. → Claims about design choices
   (thresholds τr = 0.15, τf = 0.30; 24-bit codes) were asserted, not
   justified. → **Fix:** `run_sweeps.py` (payload, threshold, strength grids),
   `run_ablation.py` (pilots, ECC, stream B, coordinate binding, layer
   interaction), runtime columns, per-scenario std in tables.

10. **Synchronization overfitted to the benchmark.** Rotation candidates were
    exactly ±5°, matching the single tested rotation attack. → Robustness to
    rotation is only demonstrated at the point the decoder was built for. →
    **Fix (partial):** candidate grid {±2°, ±5°} declared in config as an
    explicit assumption; limitation stated in the paper (Section 9).

11. **Hash-avalanche authentication.** The 24-bit block code was a hash of
    quantized features: one feature-bin drift flips ~50% of bits, so the
    mismatch-ratio threshold protected only against carrier errors, not
    feature drift. → benign FPR near quantization boundaries. → **Fix:**
    embed the Gray-coded features themselves (XOR position mask); one-bin
    drift costs exactly one bit of sixteen.

12. **No ECC / no false-match analysis for the ContentID.** → 128-bit payload
    with only carrier repetition; τr never analyzed. → **Fix:** repetition-3
    code with key interleaving and soft ML combining; analytic P_FA at τr.

13. **Copy-move GT semantics unstated.** Source region is unchanged content
    but the reader cannot tell whether it is counted. → **Fix:** explicitly
    documented (destination-only GT) in transforms and paper.

14. **Reproducibility gaps:** magic constants inline, no config file, no
    manifest, global RNG seeding, no runnable repo layout. → **Fix:**
    `config.yaml` single source of truth, keyed-PRF randomness only, JSON
    manifest per run, `scripts/run_all.sh` regenerates everything.

## Presentation

15. Overclaiming language ("highly robust", "highly recoverable under all
    attacks") replaced by threshold-conditioned, false-alarm-bounded
    statements; PSNR 33.6 dB presented as one point on a measured
    quality–robustness frontier rather than defended in isolation.
