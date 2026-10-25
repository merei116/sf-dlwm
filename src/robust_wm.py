"""Robust ContentID watermark (Layer R).

Design summary
--------------
* Payload: L-bit ContentID fingerprint, protected by a rate-1/r repetition
  code with key-dependent interleaving (src/ecc.py).
* Pilot sequence: n_p key-derived bits, KNOWN TO THE VERIFIER FROM THE KEY
  ALONE (independent of the payload). Pilots serve two purposes:
    1. blind geometric synchronization: candidate inverse transforms are
       ranked by pilot BER, never by the expected payload;
    2. watermark-presence hypothesis test with an analytically computable
       false-alarm probability.
  This replaces the oracle extraction of the original codebase, in which
  synchronization candidates were scored against the expected payload bits.
* Two carrier streams:
    Stream A - low/mid frequency DCT pairs over the full frame
               (compression / filtering resilience).
    Stream B - mid frequency DCT pairs replicated in nested central regions
               (crop resilience via redundant spatial anchoring).
* Embedding rule: differential (relative-magnitude) modulation of a
  key-selected coefficient pair with a locally adaptive margin.

All schedules depend only on (key, image size, payload length, config), so the
decoder is fully blind given the key and the registered image size.
"""
from dataclasses import dataclass, field
import numpy as np
import cv2

from .keys import prf_rng, prf_bits
from . import ecc

PAIRS_A = [((2, 1), (1, 2)), ((3, 1), (1, 3)), ((2, 2), (3, 0)), ((0, 3), (3, 0))]
PAIRS_B = [((3, 4), (4, 3)), ((2, 5), (5, 2)), ((3, 5), (5, 3)), ((2, 4), (4, 2))]
BLOCK = 8


@dataclass
class RobustConfig:
    payload_bits: int = 64
    pilot_bits: int = 16
    ecc_rate: int = 3
    strength: float = 34.0
    repeats_a: int = 10          # carriers per coded bit, stream A
    repeats_b: int = 4           # carriers per coded bit, per stream-B region
    crop_ratios: tuple = (1.00, 0.85, 0.72)
    ber_threshold: float = 0.20  # payload verification threshold (tau_r)
    pilot_threshold: float = 0.25  # presence/sync threshold (tau_p)
    sync_rotations: tuple = (-5.0, -2.0, 2.0, 5.0)
    sync_crop_ratios: tuple = (0.90, 0.85, 0.75)
    use_stream_b: bool = True    # ablation switch
    use_pilot_sync: bool = True  # ablation switch (False: rank by confidence)


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def _to_y(img):
    ycc = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2YCrCb)
    return ycc, ycc[:, :, 0].astype(np.float32)


def _valid(h, w):
    return h - h % BLOCK, w - w % BLOCK


def _region_coords(h8, w8, ratio):
    """Block-aligned coordinates of the centered region of the given ratio."""
    if ratio >= 0.999:
        rows = range(BLOCK, h8 - BLOCK, BLOCK)
        cols = range(BLOCK, w8 - BLOCK, BLOCK)
    else:
        rh = int(round(h8 * ratio)) // BLOCK * BLOCK
        rw = int(round(w8 * ratio)) // BLOCK * BLOCK
        r0 = ((h8 - rh) // 2) // BLOCK * BLOCK
        c0 = ((w8 - rw) // 2) // BLOCK * BLOCK
        rows = range(r0, min(h8, r0 + rh), BLOCK)
        cols = range(c0, min(w8, c0 + rw), BLOCK)
    return [(r, c) for r in rows for c in cols]


# --------------------------------------------------------------------------
# carrier schedules
# --------------------------------------------------------------------------

def _coded_sequence(payload, cfg: RobustConfig, key):
    """[pilots | interleaved ECC(payload)] -> coded bit sequence."""
    pilots = prf_bits(key, "pilot", n_bits=cfg.pilot_bits)
    coded_payload = ecc.encode(payload, cfg.ecc_rate, key)
    return np.concatenate([pilots, coded_payload]), pilots


def _n_coded(cfg: RobustConfig):
    return cfg.pilot_bits + cfg.payload_bits * cfg.ecc_rate


def _schedule(h, w, cfg: RobustConfig, key, stream: str, ratio: float, repeats: int):
    """Deterministic carrier schedule for one stream/region.

    Returns a list of (coded_bit_index, r, c, q1, q2). Carriers are drawn
    without replacement when possible so distinct coded bits do not collide
    on the same coefficient pair.
    """
    h8, w8 = _valid(h, w)
    pairs = PAIRS_A if stream == "A" else PAIRS_B
    carriers = [(r, c, q1, q2) for (r, c) in _region_coords(h8, w8, ratio)
                for (q1, q2) in pairs]
    n_coded = _n_coded(cfg)
    total = n_coded * repeats
    rng = prf_rng(key, "sched", stream, ratio, h, w, n_coded, repeats)
    replace = total > len(carriers)
    sel = rng.choice(len(carriers), size=total, replace=replace)
    items = [(t % n_coded, *carriers[int(s)]) for t, s in enumerate(sel)]
    rng.shuffle(items)
    return items


def full_schedule(h, w, cfg: RobustConfig, key):
    items = _schedule(h, w, cfg, key, "A", 1.0, cfg.repeats_a)
    if cfg.use_stream_b:
        for ratio in cfg.crop_ratios:
            items += _schedule(h, w, cfg, key, "B", ratio, cfg.repeats_b)
    return items


# --------------------------------------------------------------------------
# embedding
# --------------------------------------------------------------------------

def _adaptive_delta(dct, strength):
    """Locally adaptive margin: larger in textured blocks, bounded both ways."""
    energy = float(np.mean(np.abs(dct[1:6, 1:6])))
    scale = np.clip(energy / 30.0, 0.9, 2.4)
    return strength * scale


def embed(img, payload, key, cfg: RobustConfig):
    """Embed pilots + coded payload. Returns the watermarked RGB image."""
    img = np.asarray(img, dtype=np.uint8)
    h, w = img.shape[:2]
    h8, w8 = _valid(h, w)
    coded, _ = _coded_sequence(np.asarray(payload, np.uint8), cfg, key)
    ycc, y = _to_y(img)
    y = y[:h8, :w8].copy()
    for bit_idx, r, c, q1, q2 in full_schedule(h, w, cfg, key):
        patch = y[r:r + BLOCK, c:c + BLOCK]
        if patch.shape != (BLOCK, BLOCK):
            continue
        dct = cv2.dct(patch)
        delta = _adaptive_delta(dct, cfg.strength)
        a, b = float(dct[q1]), float(dct[q2])
        avg = (a + b) / 2.0
        if coded[bit_idx] == 1:
            dct[q1], dct[q2] = avg + delta / 2, avg - delta / 2
        else:
            dct[q1], dct[q2] = avg - delta / 2, avg + delta / 2
        y[r:r + BLOCK, c:c + BLOCK] = cv2.idct(dct)
    ycc[:h8, :w8, 0] = np.clip(y, 0, 255).astype(np.uint8)
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _raw_scores(y, items, n_coded, clip=90.0):
    """Accumulate trimmed carrier margins per coded bit position."""
    per_bit = [[] for _ in range(n_coded)]
    for bit_idx, r, c, q1, q2 in items:
        patch = y[r:r + BLOCK, c:c + BLOCK]
        if patch.shape != (BLOCK, BLOCK):
            continue
        dct = cv2.dct(patch)
        per_bit[bit_idx].append(float(np.clip(float(dct[q1] - dct[q2]), -clip, clip)))
    scores = np.zeros(n_coded, dtype=np.float64)
    for i, s in enumerate(per_bit):
        if not s:
            continue
        arr = np.asarray(s, dtype=np.float64)
        if arr.size >= 12:  # trimmed mean vs. outlier carriers
            lo, hi = np.percentile(arr, [10, 90])
            tr = arr[(arr >= lo) & (arr <= hi)]
            if tr.size:
                arr = tr
        scores[i] = float(np.mean(arr))
    return scores


def _decode_candidate(y, h, w, cfg, key, pilots):
    items = full_schedule(h, w, cfg, key)
    scores = _raw_scores(y, items, _n_coded(cfg))
    pilot_scores = scores[:cfg.pilot_bits]
    pilot_hat = (pilot_scores >= 0).astype(np.uint8)
    pilot_ber = float(np.mean(pilot_hat != pilots))
    bits, conf = ecc.decode_soft(scores[cfg.pilot_bits:], cfg.payload_bits,
                                 cfg.ecc_rate, key)
    mean_conf = float(np.mean(conf))
    return bits, pilot_ber, mean_conf


def _resize_to(img, shape):
    h, w = shape[:2]
    if img.shape[:2] == (h, w):
        return img.astype(np.uint8)
    return cv2.resize(img.astype(np.uint8), (w, h), interpolation=cv2.INTER_CUBIC)


def _rotate(img, angle):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REFLECT)


def _inverse_crop(img, shape, ratio):
    """Hypothesis: received image is a centered crop of ratio `ratio`,
    re-expanded to full size. Invert by shrinking back onto a canvas."""
    h, w = shape[:2]
    base = _resize_to(img, shape)
    ch = max(BLOCK, int(round(h * ratio)) // 2 * 2)
    cw = max(BLOCK, int(round(w * ratio)) // 2 * 2)
    small = cv2.resize(base, (cw, ch), interpolation=cv2.INTER_AREA)
    canvas = np.full((h, w, 3), 127, dtype=np.uint8)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    canvas[y0:y0 + ch, x0:x0 + cw] = small
    return canvas


def _sync_candidates(img, shape, cfg: RobustConfig):
    base = _resize_to(img, shape)
    cand = [("identity", base)]
    for a in cfg.sync_rotations:
        cand.append((f"rot{a:+.0f}", _rotate(base, a)))
    for r in cfg.sync_crop_ratios:
        cand.append((f"inv_crop_{r:.2f}", _inverse_crop(base, shape, r)))
    return cand


def extract(img, registered_shape, key, cfg: RobustConfig):
    """Blind extraction. Only uses: the received image, the secret key, the
    registered image size, and the public configuration. Never sees the
    expected payload.

    Returns dict with decoded bits, pilot BER of the selected candidate,
    candidate name, and mean soft confidence.
    """
    pilots = prf_bits(key, "pilot", n_bits=cfg.pilot_bits)
    h, w = registered_shape[:2]
    best = None
    for name, cand in _sync_candidates(img, registered_shape, cfg):
        _, y = _to_y(cand)
        bits, pilot_ber, conf = _decode_candidate(y, h, w, cfg, key, pilots)
        # candidate score: pilot BER (primary), confidence (tie-break)
        score = (-pilot_ber, conf) if cfg.use_pilot_sync else (conf,)
        if best is None or score > best[0]:
            best = (score, bits, pilot_ber, conf, name)
        if cfg.use_pilot_sync and pilot_ber == 0.0:
            break  # exact pilot lock: legitimate early exit (key-derived only)
    _, bits, pilot_ber, conf, name = best
    return {"bits": bits, "pilot_ber": pilot_ber, "confidence": conf,
            "sync_candidate": name,
            "present": pilot_ber <= cfg.pilot_threshold}


def verify_against_registry(extraction, expected_payload, cfg: RobustConfig):
    """Registry-assisted decision: compare the decoded payload with the
    registered ContentID fingerprint."""
    bits = extraction["bits"]
    exp = np.asarray(expected_payload, np.uint8).ravel()
    n = min(len(bits), len(exp))
    ber = 1.0 if n == 0 else float(np.mean(bits[:n] != exp[:n]))
    a = 2.0 * bits[:n].astype(np.float64) - 1.0
    b = 2.0 * exp[:n].astype(np.float64) - 1.0
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    nc = 0.0 if denom == 0 else float(np.dot(a, b) / denom)
    detected = bool(extraction["present"] and ber <= cfg.ber_threshold)
    return {"ber": ber, "nc": nc, "detected": detected}
