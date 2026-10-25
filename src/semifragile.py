"""Semi-fragile authentication layer (Layer A).

Replaces the fragile LSB layer of the original method, which was destroyed by
any re-encoding (JPEG, resize) and silently fell back to a non-watermark
pixel-statistics heuristic. Design:

* 16x16 authentication blocks, each split into four 8x8 sub-blocks.
* Feature code f_i (m = 16 bits): the mean luminance of each 8x8 sub-block,
  quantized with step q_feat and Gray-coded on 4 bits. Gray coding makes a
  one-bin drift cost exactly one bit, so benign perturbations degrade the
  code gracefully instead of avalanching (as a hash would).
  Means depend only on the DC coefficient, so the layer's own mid-frequency
  embedding does not perturb the features (no circular dependency).
* Coordinate binding: the embedded code is e_i = f_i XOR PRF(K, r, c).
  Content copied to another location decodes against the wrong mask and
  yields ~50% mismatch, which exposes copy-move edits.
* Embedding: dithered scalar QIM with step Delta_a on four mid-frequency DCT
  coefficients per 8x8 sub-block (positions disjoint from the robust layer's
  coefficient pairs). Delta_a controls the JPEG tolerance class.
* Verification (tri-state):
    - median block mismatch > tau_u  -> "unverifiable" (global desync or
      out-of-tolerance re-encoding); no tamper map is emitted;
    - otherwise blocks with mismatch ratio >= tau_f are flagged; the block
      map is cleaned by morphological open/close and upsampled.

Unlike the original code, there is NO hidden pixel-statistics anomaly
detector: every localization decision is traceable to the watermark.
"""
from dataclasses import dataclass
import numpy as np
import cv2

from .keys import prf_bits

AUTH_POS = [(2, 3), (3, 2), (1, 4), (4, 1)]  # disjoint from PAIRS_A / PAIRS_B
ABLOCK = 16
SUB = 8


@dataclass
class AuthConfig:
    delta: float = 26.0        # QIM step (JPEG tolerance class)
    q_feat: float = 16.0       # feature quantization step (luminance means)
    tau_f: float = 0.30        # per-block tamper threshold
    tau_u: float = 0.40        # global unverifiability threshold (median rho)
    tau_g: float = 0.35        # max flagged fraction under the localized-
                               # tampering assumption; above -> unverifiable
    min_component_blocks: int = 2
    coordinate_binding: bool = True   # ablation switch
    morph_cleanup: bool = True


def _gray4(v):
    v = int(np.clip(v, 0, 15))
    g = v ^ (v >> 1)
    return [(g >> k) & 1 for k in (3, 2, 1, 0)]


def _sub_offsets():
    return [(0, 0), (0, SUB), (SUB, 0), (SUB, SUB)]


def _features(y_block, q_feat):
    """16-bit Gray-coded feature vector from the four sub-block means."""
    bits = []
    for dy, dx in _sub_offsets():
        m = float(np.mean(y_block[dy:dy + SUB, dx:dx + SUB]))
        bits += _gray4(round(m / q_feat))
    return np.asarray(bits, dtype=np.uint8)


def _mask(key, r, c, m=16):
    return prf_bits(key, "auth", r, c, n_bits=m)


def _qim_embed(coef, bit, delta):
    d = delta / 2.0 if bit else 0.0
    return delta * np.round((coef - d) / delta) + d


def _qim_extract(coef, delta):
    e0 = abs(coef - delta * np.round(coef / delta))
    e1 = abs(coef - (delta * np.round((coef - delta / 2) / delta) + delta / 2))
    return 1 if e1 < e0 else 0


def embed(img, key, cfg: AuthConfig):
    """Embed the authentication layer into the (robust-marked) RGB image."""
    img = np.asarray(img, dtype=np.uint8)
    out_ycc = cv2.cvtColor(img, cv2.COLOR_RGB2YCrCb)
    y = out_ycc[:, :, 0].astype(np.float32)
    h, w = y.shape
    h0, w0 = h - h % ABLOCK, w - w % ABLOCK
    for r in range(0, h0, ABLOCK):
        for c in range(0, w0, ABLOCK):
            block = y[r:r + ABLOCK, c:c + ABLOCK]
            code = _features(block, cfg.q_feat)
            if cfg.coordinate_binding:
                code = code ^ _mask(key, r, c)
            k = 0
            for dy, dx in _sub_offsets():
                patch = block[dy:dy + SUB, dx:dx + SUB]
                dct = cv2.dct(patch)
                for pos in AUTH_POS:
                    dct[pos] = _qim_embed(float(dct[pos]), int(code[k]), cfg.delta)
                    k += 1
                block[dy:dy + SUB, dx:dx + SUB] = cv2.idct(dct)
            y[r:r + ABLOCK, c:c + ABLOCK] = block
    out_ycc[:, :, 0] = np.clip(y, 0, 255).astype(np.uint8)
    return cv2.cvtColor(out_ycc, cv2.COLOR_YCrCb2RGB)


def _mismatch_map(img, key, cfg: AuthConfig):
    y = cv2.cvtColor(np.asarray(img, np.uint8), cv2.COLOR_RGB2YCrCb)[:, :, 0].astype(np.float32)
    h, w = y.shape
    h0, w0 = h - h % ABLOCK, w - w % ABLOCK
    br, bc = h0 // ABLOCK, w0 // ABLOCK
    rho = np.zeros((br, bc), dtype=np.float32)
    for bi, r in enumerate(range(0, h0, ABLOCK)):
        for bj, c in enumerate(range(0, w0, ABLOCK)):
            block = y[r:r + ABLOCK, c:c + ABLOCK]
            feat = _features(block, cfg.q_feat)
            if cfg.coordinate_binding:
                feat = feat ^ _mask(key, r, c)
            extracted = []
            for dy, dx in _sub_offsets():
                dct = cv2.dct(block[dy:dy + SUB, dx:dx + SUB])
                extracted += [_qim_extract(float(dct[pos]), cfg.delta) for pos in AUTH_POS]
            rho[bi, bj] = float(np.mean(feat != np.asarray(extracted, np.uint8)))
    return rho


def _cleanup(mask_blocks, cfg: AuthConfig):
    u = (mask_blocks.astype(np.uint8)) * 255
    if cfg.morph_cleanup and u.size:
        k = np.ones((3, 3), np.uint8)
        u = cv2.morphologyEx(u, cv2.MORPH_CLOSE, k)
        u = cv2.morphologyEx(u, cv2.MORPH_OPEN, k)
    keep = np.zeros_like(mask_blocks, dtype=bool)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(u, 8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= cfg.min_component_blocks:
            keep[lab == i] = True
    return keep


def verify(img, key, cfg: AuthConfig):
    """Tri-state verification. Returns dict:
       status in {authentic, tampered, unverifiable},
       tamper_map (uint8 HxW, 255 = tampered), block mismatch stats."""
    img = np.asarray(img, dtype=np.uint8)
    h, w = img.shape[:2]
    rho = _mismatch_map(img, key, cfg)
    median_rho = float(np.median(rho)) if rho.size else 1.0
    tamper_map = np.zeros((h, w), dtype=np.uint8)
    if median_rho > cfg.tau_u:
        return {"status": "unverifiable", "tamper_map": tamper_map,
                "median_rho": median_rho, "flagged_ratio": 0.0}
    flagged = _cleanup(rho >= cfg.tau_f, cfg)
    if flagged.size and float(flagged.mean()) > cfg.tau_g:
        # Localized-tampering assumption violated: most of the frame is
        # inconsistent, so the evidence indicates global re-processing beyond
        # the tolerance class rather than a local edit.
        return {"status": "unverifiable", "tamper_map": tamper_map,
                "median_rho": median_rho, "flagged_ratio": float(flagged.mean())}
    for bi in range(flagged.shape[0]):
        for bj in range(flagged.shape[1]):
            if flagged[bi, bj]:
                tamper_map[bi * ABLOCK:(bi + 1) * ABLOCK,
                           bj * ABLOCK:(bj + 1) * ABLOCK] = 255
    status = "tampered" if flagged.any() else "authentic"
    return {"status": status, "tamper_map": tamper_map,
            "median_rho": median_rho,
            "flagged_ratio": float(flagged.mean()) if flagged.size else 0.0}
