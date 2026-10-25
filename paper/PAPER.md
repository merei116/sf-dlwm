# SF-DLWM: A Reproducible Dual-Layer Watermarking Framework Combining Pilot-Synchronized Robust Provenance Recovery with Semi-Fragile Tamper Localization

**Rzayeva Leila, Zhaparkhanova Merei, Batkuldin Alisher, Lisnevskyi Rostyslav, Mohammad Ragab**

*Rewritten version. All empirical values marked [TO BE COMPUTED] must be filled from `results/table_*.csv` after running `scripts/run_all.sh` on the final dataset. Values from the smoke run on the synthetic fallback dataset must not be transferred into this paper.*

---

## Abstract

Images circulating through messaging and social-media platforms undergo benign re-encoding (JPEG compression, resizing, cropping) that breaks cryptographic integrity checks, while malicious local edits (copy-move, inpainting) must still be detected and localized. We present SF-DLWM, a dual-layer watermarking framework that separates these two functions into independently evaluable mechanisms. The robust layer embeds a 64-bit ContentID fingerprint via differential DCT-coefficient modulation, protected by a repetition code and accompanied by key-derived *pilot bits* that provide (i) blind geometric synchronization and (ii) a watermark-presence hypothesis test with an analytic false-alarm bound of 2.3×10⁻⁷ at the operating threshold. The authentication layer replaces conventional fragile LSB marking with a *semi-fragile* design: Gray-coded quantized luminance features, XOR-bound to the block position under a keyed PRF, embedded by quantization index modulation (QIM) in mid-frequency DCT coefficients. The layer tolerates a declared class of benign re-encodings (JPEG quality ≥ [TO BE COMPUTED], platform-like recompression) while flagging local edits, and issues a *tri-state* verdict — authentic, tampered (with a localization map), or unverifiable — instead of emitting unreliable maps under out-of-tolerance processing. Extraction is fully blind: unlike a common evaluation flaw we identify and correct, the expected payload is never used to steer synchronization or decoding. On [DATASET, N images] × 21 scenarios, the robust layer achieves a detection rate of [TO BE COMPUTED] at mean payload BER [TO BE COMPUTED], with [TO BE COMPUTED] false detections in wrong-key and unwatermarked negative controls; the authentication layer attains copy-move IoU [TO BE COMPUTED] and inpainting IoU [TO BE COMPUTED] at benign false-positive rate [TO BE COMPUTED], compared against a fairly synchronized LL01-style dual-layer baseline and a perceptual-hash baseline. All code, configurations, seeds and scripts to regenerate every table and figure are released.

**Keywords:** digital image watermarking; semi-fragile watermarking; tamper localization; provenance verification; QIM; DCT; reproducibility

---

## 1. Introduction

Digital images serve as evidence, documentation and decision-support inputs in forensic, compliance and media workflows. Two properties of modern image circulation make integrity verification hard. First, *benign* processing is ubiquitous: messaging and social platforms recompress, resize and crop every uploaded image, so any byte-exact mechanism (hashes, signatures) fails on content that is semantically unchanged. Second, *malicious* local manipulation — copy-move, splicing, inpainting — can alter image semantics while preserving overall appearance. A practical verification mechanism must therefore answer two different questions about a received image: **(Q1)** *is this the registered content?* (provenance recovery under benign transformations) and **(Q2)** *has any region been locally edited?* (tamper detection and localization).

Watermarking research addresses Q1 with robust schemes and Q2 with fragile or semi-fragile schemes, and the two goals pull the design in opposite directions: robustness to processing suppresses sensitivity to edits, and vice versa. Hybrid schemes that embed both a robust and a fragile mark exist since Lu and Liao [26], but — as we argue in Section 3 — the literature still lacks a *transparent, reproducible* reference design in which the two functions are cleanly separated, both are evaluated blindly under one protocol with negative controls, and the authentication layer states honestly *when it cannot decide*.

This paper is a redesigned and re-evaluated successor of our earlier dual-layer framework. In auditing that work we found methodological flaws that are easy to commit and rarely reported: the decoder's geometric-synchronization search was scored against the *expected* payload (an oracle that inflates robustness results to perfection); the fragile LSB layer was destroyed by every re-encoding and silently replaced by an undocumented pixel-statistics heuristic; and the baseline received no synchronization at all. SF-DLWM removes all three flaws by construction and turns their absence into checkable properties: pilot-based blind synchronization, a purely watermark-based semi-fragile authentication layer with a tri-state output, and a shared synchronization budget for all methods. We consider this corrective redesign, together with the released benchmark, a contribution in itself.

The research question is: **RQ.** Under a unified blind protocol with negative controls, to what extent can a dual-layer design simultaneously deliver (a) registry-assisted ContentID recovery across benign and platform-like transformations at a bounded false-alarm rate, and (b) localized tamper maps that remain reliable under mild re-encoding, while degrading *gracefully to a declared "unverifiable" state* — rather than emitting false maps — outside its tolerance class?

## 2. Related Work

**Robust watermarking.** Spread-spectrum embedding in perceptually significant components [4] and telltale transform-domain designs [7,8] established the robust paradigm; modern variants combine DWT/DCT/SVD, feature points and moments to trade off robustness, imperceptibility and security [9–12]. Robust schemes answer Q1 but provide little spatial information about edits, and their evaluation frequently omits false-alarm analysis: a detection rate reported without a matched negative control (wrong key, unwatermarked content) is not a detection claim in the statistical sense.

**Fragile and semi-fragile authentication.** Fragile schemes [13–16] detect any modification but false-alarm on benign processing; attacks on early designs [18,19] additionally showed the need for keyed, position-bound authentication codes. Semi-fragile schemes tolerate a declared class of incidental distortions — canonically JPEG up to a quality bound [17] — while reacting to content edits; recent work improves localization and recovery via SVD block signatures, self-embedding, reversible codes and learned localizers [20–25]. Two recurring weaknesses remain. First, hash-based block codes avalanche under one-bin feature drift, so benign processing near quantization boundaries produces all-or-nothing block failures. Second, most schemes emit a tamper map unconditionally, even when the whole frame is out of tolerance, which yields the high false-positive rates repeatedly reported outside nominal conditions.

**Hybrid dual-purpose schemes.** Multipurpose robust+fragile systems [26–31] demonstrate feasibility, often adding self-recovery, chaotic maps or application-specific (medical ROI) machinery. Their complexity impedes replication, and their evaluations rarely include blind synchronization, negative controls, or availability reporting for the authentication function.

**Provenance infrastructure and non-watermark alternatives.** Registry- and manifest-based provenance is complementary: watermarks bind an identifier *into* the pixels so it survives metadata stripping, and the registry supplies the expected identifier at verification. Perceptual hashing answers a weaker form of Q1 without embedding and is included here as a baseline; QIM [32] provides the information-embedding foundation of our authentication layer.

## 3. Research Gap and Contributions

The gap is not the absence of robust, fragile or hybrid methods, but the absence of a *defensible reference design and benchmark* with the following joint properties, none of which is standard in the hybrid literature: (1) extraction that is provably blind (no oracle access to the expected payload during synchronization or decoding); (2) detection claims accompanied by analytic and empirical false-alarm rates; (3) an authentication layer whose tolerance class is declared and calibrated, and which reports *unverifiable* instead of guessing when that class is exceeded; (4) baselines granted the same synchronization budget; (5) a fully scripted pipeline regenerating every reported number.

Contributions:

- **C1 (method).** A pilot-bit mechanism in the robust layer that decouples geometric synchronization and presence testing from the payload, enabling blind candidate search with a legitimate early exit and an analytic false-alarm bound (Sections 4.3, 4.6).
- **C2 (method).** A semi-fragile authentication layer built from Gray-coded quantized features XOR-bound to position under a keyed PRF and embedded by QIM: feature drift degrades gracefully (a one-bin drift costs one bit, not a hash avalanche), copy-move is exposed by the position mask, and the QIM step Δₐ sets an explicit, tunable JPEG tolerance class (Section 4.4).
- **C3 (method).** Tri-state verification semantics (authentic / tampered+map / unverifiable) with two principled unverifiability conditions — median block mismatch and a localized-tampering area bound — converting the dominant failure mode of fragile layers (dense false maps under benign re-encoding) into an explicit abstention (Section 4.5).
- **C4 (evaluation).** A unified blind benchmark over 21 scenarios including tamper-plus-recompression, with wrong-key and unwatermarked negative controls, payload/threshold/strength sweeps, an ablation isolating each component, and a *fairly synchronized* LL01-style baseline plus a pHash baseline.
- **C5 (audit).** Identification and correction of three evaluation flaws in our prior work (oracle-scored synchronization; hidden non-watermark localizer; unsynchronized baseline), with quantification of how each flaw distorts reported results.

## 4. Proposed Method

### 4.1 Verification model, notation and key assumptions

Let I ∈ ℝ^{H×W×3} be the RGB cover. A trusted registry stores, per protected image: the ContentID string, its L-bit fingerprint **w** = Φ(ContentID) ∈ {0,1}^L (the first L bits of BLAKE2b of the identifier; L = 64), and the registered size (H, W). Embedder and verifier share a secret key K; all pseudo-randomness is derived from a keyed PRF, PRF_K(·) = BLAKE2s(key = K; domain-separated context), so every schedule is deterministic given (K, H, W, L, config) and unpredictable without K (Kerckhoffs' principle; the schedule *spaces* are public). Watermarking applies the robust layer first (it must survive distribution) and the authentication layer second (it must authenticate the distributed pixels):

  I_w = E_A( E_R(I, **w**, K), K ).

The verifier receives an attacked image I_a and knows (K, H, W, **w**). Extraction is blind: **w** enters only the final registry comparison, never the decoder.

### 4.2 Robust layer: embedding

The Y channel of YCrCb is partitioned into 8×8 blocks; C_i = DCT(B_i). The transmitted sequence is

  **s** = [ **p** ‖ π_K( rep_r(**w**) ) ],  |**s**| = n_p + rL,

where **p** = PRF_K("pilot") ∈ {0,1}^{n_p} (n_p = 16) are *pilot bits known from the key alone*, rep_r is an r-fold repetition code (r = 3) and π_K a key-dependent interleaver. Two carrier streams embed **s**:

- **Stream A** (compression resilience): coefficient pairs P_A = {((2,1),(1,2)), ((3,1),(1,3)), ((2,2),(3,0)), ((0,3),(3,0))} over the full frame, R_A = 10 carriers per coded bit.
- **Stream B** (crop anchoring): pairs P_B = {((3,4),(4,3)), ((2,5),(5,2)), ((3,5),(5,3)), ((2,4),(4,2))} replicated inside nested centered regions of ratios ρ ∈ {1.00, 0.85, 0.72}, R_B = 4 carriers per coded bit per region, so at least one complete copy of **s** remains spatially anchored after centered cropping down to ratio ≈ 0.72.

Carrier assignment is a PRF-seeded draw (without replacement while capacity permits) per stream/region. For a carrier in block i with pair (q₁, q₂) carrying coded bit s_t, let c₁ = C_i(q₁), c₂ = C_i(q₂), a = (c₁ + c₂)/2:

  s_t = 1 ⇒ (c₁, c₂) ← (a + Δ_i/2, a − Δ_i/2);  s_t = 0 ⇒ (c₁, c₂) ← (a − Δ_i/2, a + Δ_i/2),

with locally adaptive margin Δ_i = α · clip(Ē_i / 30, 0.9, 2.4), where Ē_i is the mean |AC| magnitude of the low band and α the base strength (default 34). The margin grows in textured blocks (perceptual masking) and is bounded in smooth blocks (imperceptibility).

**Pseudocode (embedding).**
```
EmbedRobust(I, w, K):
  s ← [ PRF_K("pilot") ‖ Interleave_K(Repeat_r(w)) ]
  for (t, block i, pair (q1,q2)) in Schedule_K(H, W; streams A, B):
      C ← DCT(block i);  Δ ← AdaptiveMargin(C, α)
      enforce sign(C[q1] − C[q2]) with magnitude Δ according to s[t]
      block i ← IDCT(C)
  return image
```

### 4.3 Robust layer: blind synchronized extraction

Given I_a, the decoder forms geometric candidates: identity resize to (H, W); inverse rotations {±2°, ±5°}; inverse centered crops of ratios {0.90, 0.85, 0.75}. For each candidate it accumulates, per coded position t, the trimmed-mean margin score σ_t = trimmean{ clip(C_i(q₁) − C_i(q₂), ±90) } over that position's carriers, decodes the pilots as p̂_t = 1[σ_t ≥ 0] for t ≤ n_p, and computes the pilot BER β_p. **Candidates are ranked by β_p** (soft confidence breaks ties); β_p = 0 permits early exit — legitimately, since pilots are key-derived and payload-independent. On the winning candidate, payload scores are de-interleaved and soft-combined across the r repetitions (sum of σ, then sign), the maximum-likelihood rule for a symmetric soft channel.

This is the central corrective element of the redesign: in our prior implementation, candidates were ranked by BER against the *expected payload* with early exit at BER ≤ 0.01 — an oracle that (i) guarantees near-zero reported BER whenever any candidate is approximately correct and (ii) is unrealizable in deployment, because a real verifier that already trusted the expected payload for steering would have nothing left to verify. Pilots restore realizability at the cost of n_p carrier positions.

### 4.4 Semi-fragile authentication layer

The image is partitioned into 16×16 authentication blocks, each split into four 8×8 sub-blocks at offsets O = {(0,0),(0,8),(8,0),(8,8)}.

**Feature code.** For the block at (r, c), f_{r,c} ∈ {0,1}^{16} concatenates the 4-bit Gray codes of the quantized sub-block means, g₄(round(mean(Y_sub)/q_f)) with q_f = 16. Two properties matter: (i) means depend only on the DC coefficient while the layer embeds only in AC coefficients, so there is **no circular dependency** between features and embedding; (ii) Gray coding makes a one-bin drift cost exactly one bit of sixteen, so benign perturbation degrades the code *gracefully* — unlike a cryptographic hash of the features, which avalanches on any drift.

**Coordinate binding.** e_{r,c} = f_{r,c} ⊕ PRF_K("auth", r, c). Content copied to another location decodes against the wrong mask and yields ≈50% mismatch: copy-move detection follows from the construction rather than from ad-hoc rules, and the keyed mask also blocks the collage-style forgeries that defeated unkeyed block authentication [18,19].

**Embedding.** The 16 bits of e_{r,c} are embedded, 4 per sub-block, by dithered scalar QIM [32] with step Δₐ at mid-frequency positions {(2,3),(3,2),(1,4),(4,1)} — disjoint from P_A ∪ P_B, so the two layers never write the same coefficient:

  QIM_b(c) = Δₐ · round( (c − b·Δₐ/2) / Δₐ ) + b·Δₐ/2,  b ∈ {0,1}.

Δₐ sets the tolerance class: any re-encoding that perturbs these coefficients by less than Δₐ/4 leaves the bits decodable. The default Δₐ = 26 targets JPEG quality ≳ 70 and platform-like recompression; the threshold sweep (Section 7) reports the empirically calibrated tolerance boundary [TO BE COMPUTED].

### 4.5 Tri-state verification and localization

Per block: extract ê by minimum-distance QIM decoding, recompute f̂ from the received pixels, and form the mismatch ratio ρ_{r,c} = (1/16) Σ_j [ (f̂ ⊕ PRF_K("auth", r, c))_j ≠ ê_j ].

Decision procedure:
1. **Unverifiable (global):** median ρ over all blocks > τ_u (= 0.40) ⇒ the frame is geometrically desynchronized (crop/resize/rotation) or re-encoded beyond tolerance; no map is emitted.
2. Otherwise flag blocks with ρ ≥ τ_f (= 0.30); clean with 3×3 morphological close/open and remove connected components smaller than 2 blocks.
3. **Unverifiable (area bound):** flagged fraction > τ_g (= 0.35) ⇒ the localized-tampering assumption is violated — the evidence indicates global processing rather than a local edit; abstain.
4. Else output **tampered** with the block map upsampled to pixel resolution, or **authentic** if no block survives cleanup.

Abstention is a feature, not a failure: the characteristic pathology of fragile layers is a confident, dense, wrong map under benign re-encoding. SF-DLWM converts that regime into a declared state on which the application can act (e.g., fall back to robust-layer-only verification). We report abstention frequency (availability) as a first-class result.

**Pseudocode (verification).**
```
Verify(I_a, K, w, (H, W)):
  ext ← BlindExtract(I_a, K, (H, W))            # Section 4.3
  present  ← ext.pilot_ber ≤ τ_p
  detected ← present AND BER(ext.bits, w) ≤ τ_r  # only use of w
  auth ← TriStateAuth(I_a, K)                   # Section 4.5
  return {detected, BER, NC, auth.status, auth.map}
```

### 4.6 Detection thresholds and false-alarm analysis

Registry verification declares detection when the watermark is present (β_p ≤ τ_p = 0.25) and payload BER ≤ τ_r = 0.20. Under H₀ (no watermark, or wrong key) decoded bits are approximately i.i.d. Bernoulli(1/2), so the probability that a random payload passes the BER gate is the binomial tail

  P_FA = 2^{−L} Σ_{k ≤ ⌊τ_r L⌋} C(L, k) = 2.28×10⁻⁷ for L = 64,

computed by `metrics.random_payload_false_alarm` and validated empirically by wrong-key and unwatermarked controls (Section 6.4). The presence gate adds an independent pilot test with tail 2^{−16} Σ_{k ≤ 4} C(16, k) ≈ 3.8×10⁻².

### 4.7 What is new relative to the original paper

(1) Pilot-based blind synchronization replacing oracle-scored candidate search; (2) a semi-fragile QIM authentication layer replacing fragile LSB marking, which any JPEG destroys; (3) graceful Gray-coded feature codes replacing avalanche-prone hashes; (4) tri-state semantics with two unverifiability conditions replacing unconditional map emission; (5) removal of the undocumented pixel-statistics anomaly detector — every localization decision is now watermark-traceable; (6) explicit ECC with soft combining; (7) analytic and empirical false-alarm treatment; (8) fair baseline synchronization; (9) tamper-plus-recompression scenarios; (10) a scripted sweep/ablation/negative-control protocol.

## 5. Experimental Setup

**Dataset.** [TO BE COMPUTED: final dataset — e.g., the USC-SIPI miscellaneous volume [33], N images, with a content-diversity statement]. Images are resized to 512×512. The released code labels every result row with the dataset actually used; if the real-image directory is empty it generates a clearly labeled deterministic synthetic fallback, structurally eliminating dataset/claim mismatches.

**Scenarios (21).** Benign (17): identity; JPEG {95, 85, 70, 50, 30}; resize {0.90, 0.75, 0.50}; Gaussian blur 3×3; Gaussian noise σ = 8; centered crop 0.85; rotation 5°; telegram-like (JPEG85); whatsapp-like (resize 0.75 + JPEG65); instagram-like (center square + JPEG82); mixed instagram + crop 0.90 + JPEG70. Tampering (4): copy-move; inpainting-like (region median fill with smoothing confined to the region — the prior implementation blurred the whole frame, invalidating its own ground truth); and both followed by JPEG85. Ground truth marks the edited destination region; the copy-move *source* is unchanged content and is deliberately not counted as tampered.

**Methods.** SF-DLWM (parameters as in `config.yaml`); an LL01-style dual-layer baseline [26] (single-stream DCT differential embedding + one-bit-per-block fragile LSB) granted the *same* geometric synchronization candidates ranked by its own confidence; pHash (64 bits, Hamming threshold 10) for the identification task only.

**Metrics.** Robust layer: detection rate, BER, NC; negative-control false-detection rate. Quality: PSNR and SSIM of the watermarked image. Authentication: availability (verifiable fraction), benign FPR (flagged-pixel fraction on untampered images), and on tamper scenarios pixel-level precision, recall/TPR, FPR, F1/Dice, IoU. Runtime per stage. Spread is reported as per-scenario standard deviations across images.

**Reproducibility.** Fixed seed and key in `config.yaml`; all randomness via keyed BLAKE2s PRFs; a JSON manifest records dataset name, scenario list, seed, key fingerprint, payload length, analytic P_FA and wall time. `bash scripts/run_all.sh` regenerates every table and figure.

## 6. Results

*(All values [TO BE COMPUTED] from `results/table_*.csv` on the final dataset; table skeletons match the aggregation script's outputs. No number below may be quoted from the synthetic smoke run.)*

### 6.1 Robust recovery (Q1)

`table_robust_by_scenario`: detection rate and BER per method × scenario. The design predicts (and smoke validation on synthetic data is consistent with) sustained recovery for SF-DLWM across JPEG ≥ 30, the resize set, centered crop 0.85, rotation 5° and the platform chains, with the fairly synchronized LL01-style baseline degrading under strong recompression and mixed chains. Because our earlier report compared an oracle-synchronized proposal against an unsynchronized baseline, we additionally report the baseline *with and without* the shared synchronization budget, quantifying how much of the previously reported gap was a synchronization artifact rather than an embedding advantage [TO BE COMPUTED: both values]. pHash identification is expected to degrade specifically on crop-containing chains [TO BE COMPUTED].

### 6.2 Authentication availability and benign FPR

`table_auth_benign`: per scenario, the verifiable fraction and the flagged-pixel rate among verifiable images. By design, JPEG ≥ ~70 and telegram/instagram-like re-encodes should verify authentic at near-zero FPR, while blur, noise σ = 8, whatsapp-like, strong JPEG and all geometric desynchronizations should return *unverifiable* rather than false maps; the empirical tolerance boundary is [TO BE COMPUTED]. Availability is reported alongside FPR because an FPR computed only over confidently answered cases would overstate reliability.

### 6.3 Tamper localization (Q2)

`table_localization`: precision, recall/TPR, F1/Dice, IoU (± std) and FPR for copy-move, inpainting-like and their +JPEG85 variants [TO BE COMPUTED]. The baseline's fragile LSB layer collapses to ≈50% FPR under the +JPEG85 variants (LSBs randomized); SF-DLWM's QIM layer is designed to retain localization there — this contrast is the operational argument for semi-fragility. Localization granularity is bounded by the 16-px block grid: boundary blocks dominate precision loss, so we report the grid-aligned IoU upper bound alongside the measured IoU [TO BE COMPUTED].

### 6.4 Negative controls and false alarms

`table_negative_controls`: wrong-key and unwatermarked extraction over all images — false-detection rate [TO BE COMPUTED], mean payload BER (expected ≈ 0.5) and mean pilot BER (expected ≈ 0.3–0.5, consistent with Bernoulli(1/2) margins), against the analytic P_FA = 2.3×10⁻⁷. A robust-detection claim is meaningful only jointly with these numbers; we therefore treat this table as co-primary with 6.1.

### 6.5 Visual quality and runtime

`table_overall`, `table_runtime`: PSNR/SSIM per method and per-stage runtimes [TO BE COMPUTED]. Rather than defending a single operating point, the strength sweep (Section 7) reports the (α, Δₐ) quality–robustness frontier; the configuration in `config.yaml` is one point on that frontier chosen to keep PSNR above [TO BE COMPUTED] dB while sustaining the JPEG ≥ 70 tolerance class.

## 7. Ablation Study and Sensitivity

Variants (`experiments/run_ablation.py`): **no_pilot_sync** — candidates ranked by soft confidence, quantifying the pilots' synchronization value; **no_ecc** — r = 1 with the carrier budget equalized, isolating coding gain from raw redundancy; **no_stream_b** — crop anchoring removed, with expected failures on crop/mixed chains; **no_coord_binding** — position mask removed, with copy-move recall expected to collapse (copied blocks carry self-consistent codes); **no_auth_layer** — interaction check that the QIM layer does not degrade robust recovery. Results: [TO BE COMPUTED].

Sensitivity sweeps (`experiments/run_sweeps.py`): payload L ∈ {32, 64, 128} (BER/detection vs. capacity, with P_FA recomputed per L); τ_f ∈ [0.05, 0.50] (benign FPR vs. tamper recall — the operating-characteristic curve from which τ_f = 0.30 is justified rather than asserted); the (α, Δₐ) grid (PSNR/SSIM vs. robust BER and authentication tolerance). Curves: `figures/fig_sweep_*.png` [TO BE COMPUTED].

## 8. Discussion

The framework's value proposition is *separation with honest interfaces*: the robust layer answers Q1 as a hypothesis test with a stated false-alarm bound; the authentication layer answers Q2 only within a declared tolerance class and abstains outside it. This reframes the classic robustness–fragility dilemma as a measurable availability/reliability trade-off instead of a rhetorical one. The corrected baseline comparison is deliberately less flattering to our method than our previous report: granting the baseline the shared synchronization budget removes an artifact, and whatever gap remains is attributable to embedding design (dual streams, ECC, adaptive margins) — the scientifically interesting quantity. We equally state what the method does *not* do: it cannot detect edits applied before embedding, its authentication layer is unavailable under geometric desynchronization, and it makes no attempt at content self-recovery.

## 9. Limitations

(1) Localization is 16-px-block-granular; sub-block edits and boundary pixels bound achievable IoU. (2) The authentication layer abstains under geometric desynchronization (crop/resize/rotation) and out-of-tolerance re-encoding; extending semi-fragility to resampling (resampling-invariant features or re-synchronized authentication) is open. (3) The tolerance class is calibrated on standard JPEG; real platform pipelines evolve and differ across devices, so our platform-like scenarios are approximations. (4) Security analysis is limited to key dependence and false-alarm bounds; targeted attacks (QIM step estimation, margin flipping, adaptive collage) are not evaluated, and repetition coding is suboptimal — BCH or polar codes would improve the capacity–robustness frontier. (5) An adversary who tampers and then applies out-of-tolerance processing forces abstention, converting "tampered" into "unverifiable"; the tri-state semantics makes this evasion visible but not attributable. (6) The evaluation corpus [N images] remains modest; generalization claims require larger, more diverse datasets.

## 10. Conclusion

SF-DLWM is a reproducible dual-layer watermarking reference design: pilot-synchronized, ECC-protected robust ContentID recovery with analytic and empirical false-alarm control, combined with a semi-fragile, coordinate-bound QIM authentication layer offering tri-state semantics and watermark-traceable localization. Beyond the method itself, the paper documents and corrects three evaluation flaws (oracle-scored synchronization, a hidden non-watermark localizer, an unsynchronized baseline) whose combined effect in our earlier work was a perfect-looking but unrealizable system. Every number in this paper regenerates from `scripts/run_all.sh`. Future work: stronger channel codes, resampling-tolerant authentication features, confidence-valued tamper maps, adversarial evaluation, and validation on live platform pipelines.

## References

[1] Potdar, V. M.; Han, S.; Chang, E. A survey of digital image watermarking techniques. Proc. IEEE INDIN 2005, 709–716.
[2] Boujerfaoui, S.; Riad, R.; Douzi, H.; Ros, F.; Harba, R. Image watermarking between conventional and learning-based techniques: A literature review. Electronics 2023, 12, 74.
[3] Sharma, S.; Zou, J. J.; Fang, G.; Shukla, P.; Cai, W. A review of image watermarking for identity protection and verification. Multimed. Tools Appl. 2024, 83, 31829–31891.
[4] Cox, I. J.; Kilian, J.; Leighton, F. T.; Shamoon, T. Secure spread spectrum watermarking for multimedia. IEEE Trans. Image Process. 1997, 6, 1673–1687.
[7] Kundur, D.; Hatzinakos, D. Towards a telltale watermarking technique for tamper-proofing. Proc. ICIP 1998, 409–413.
[8] Kundur, D.; Hatzinakos, D. Digital watermarking for telltale tamper proofing and authentication. Proc. IEEE 1999, 87, 1167–1180.
[9] Hamidi, M.; El Haziti, M.; Cherifi, H.; El Hassouni, M. A hybrid robust image watermarking method based on DWT-DCT and SIFT. J. Imaging 2021, 7, 218.
[10] Hosny, K. M.; Darwish, M. M. Robust color image watermarking using multiple fractional-order moments and chaotic map. Multimed. Tools Appl. 2022, 81, 24347–24375.
[11] Elbasi, E.; Mostafa, N.; Cina, E. Robust, secure and semi-blind watermarking technique using flexible scaling factor. Electronics 2022, 11, 3680.
[12] Awasthi, D.; Srivastava, V. K. Robust, imperceptible and optimized watermarking of DICOM image using Schur decomposition, LWT-DCT-SVD. Multimed. Tools Appl. 2023, 82, 16555–16589.
[13] Yeung, M. M.; Mintzer, F. An invisible watermarking technique for image verification. Proc. ICIP 1997, 680–683.
[14] Wong, P. W. A public key watermark for image verification and authentication. Proc. ICIP 1998, 455–459.
[15] Fridrich, J. Image watermarking for tamper detection. Proc. ICIP 1998, 404–408.
[16] Fridrich, J.; Goljan, M. Images with self-correcting capabilities. Proc. ICIP 1999, 792–796.
[17] Lin, C.-Y.; Chang, S.-F. A robust image authentication method distinguishing JPEG compression from malicious manipulation. IEEE Trans. Circuits Syst. Video Technol. 2001, 11, 153–168.
[18] Fridrich, J.; Goljan, M.; Memon, N. Further attacks on Yeung–Mintzer fragile watermarking scheme. SPIE Security and Watermarking of Multimedia Contents 2000, 428–437.
[19] Fridrich, J.; Goljan, M.; Memon, N. Cryptanalysis of the Yeung–Mintzer fragile watermarking technique. J. Electron. Imaging 2002, 11, 262–274.
[20] Ansari, I. A.; Pant, M.; Ahn, C. W. SVD based fragile watermarking scheme for tamper localization and self-recovery. Int. J. Mach. Learn. Cybern. 2016, 7, 1225–1239.
[21] Kim, C.; Yang, C.-N. Self-embedding fragile watermarking scheme using AMBTC and OPAP. Appl. Sci. 2021, 11, 1146.
[22] Zhan, C.; Leng, L.; Chang, C.-C.; Horng, J.-H. Reversible image fragile watermarking with dual tampering detection. Electronics 2024, 13, 1884.
[23] Bouarroudj, R.; Souami, F.; Bellala, F. Z.; Zerrouki, N.; Harrou, F.; Sun, Y. Secure and reversible fragile watermarking for medical images. Comput. Electr. Eng. 2025, 123, 110072.
[24] Palani, A.; Agilandeeswari, L. Optimal semi-fragile watermarking based on maximum entropy random walk and Swin transformer. IEEE Access 2024, 12, 37757–37781.
[25] Amrullah, A.; Ernawan, F. Semi-fragile image watermarking using quantization-based DCT for tamper localization. Comput. Mater. Continua 2026, 86, 1–16.
[26] Lu, C.-S.; Liao, H.-Y. M. Multipurpose watermarking for image authentication and protection. IEEE Trans. Image Process. 2001, 10, 1579–1592.
[27] Ur Rahman, A.; Sultan, K.; Musleh, D.; Aldhafferi, N.; Alqahtani, A.; Mahmud, M. Robust and fragile medical image watermarking: A joint venture of coding and chaos theories. J. Healthc. Eng. 2018, 8137436.
[28] Sinhal, R.; Ansari, I. A. Multipurpose image watermarking: Ownership check, tamper detection and self-recovery. Circuits Syst. Signal Process. 2022, 41, 3199–3221.
[29] Shi, H.; Yan, K.; Geng, J.; Ren, Y. A cross-embedding based medical image tamper detection and self-recovery watermarking scheme. Multimed. Tools Appl. 2024, 83, 30319–30360.
[30] Vaidya, S. P.; et al. A robust fragile watermarking approach for image tampering detection and restoration utilizing hybrid transforms. Sci. Rep. 2025, 15, 17645.
[31] Cedillo-Hernandez, M.; et al. Semi-fragile watermarking scheme for high-resolution color images: Tamper identification, ownership authentication, and self-recovery. Algorithms 2026, 19, 28.
[32] Chen, B.; Wornell, G. W. Quantization index modulation: A class of provably good methods for digital watermarking and information embedding. IEEE Trans. Inf. Theory 2001, 47, 1423–1443.
[33] University of Southern California, Signal and Image Processing Institute. USC-SIPI Image Database. https://sipi.usc.edu/database/.
