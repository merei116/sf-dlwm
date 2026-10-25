"""LL01-style dual-layer baseline (inspired by Lu & Liao, 2001).

Simple re-implementation of the dual robust/fragile idea: a single-stream DCT
differential watermark plus a one-bit-per-block fragile LSB authentication
layer. Included as a prior-method reference.

Fairness fixes relative to the original benchmark:
  * the baseline receives the SAME geometric synchronization candidates as
    the proposed method, ranked by its own extraction confidence (the
    original benchmark gave the baseline no synchronization at all while the
    proposed method used oracle-assisted synchronization);
  * no method receives the expected payload during extraction.
"""
import hashlib
import numpy as np
import cv2

from .keys import prf_rng
from .robust_wm import _sync_candidates, RobustConfig


def _y(img):
    ycc = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2YCrCb)
    return ycc, ycc[:, :, 0].astype(np.float32)


def embed_robust(img, bits, key, strength=22.0, block=8, q1=(3, 4), q2=(4, 3)):
    img = img.copy().astype(np.uint8)
    h, w = img.shape[:2]
    h8, w8 = h - h % block, w - w % block
    ycc, y = _y(img)
    y = y[:h8, :w8].copy()
    bits = np.asarray(bits, np.uint8).ravel()
    coords = [(r, c) for r in range(block, h8 - block, block)
              for c in range(block, w8 - block, block)]
    prf_rng(key, "ll01").shuffle(coords)
    for idx, (r, c) in enumerate(coords):
        bit = bits[idx % len(bits)]
        dct = cv2.dct(y[r:r + block, c:c + block])
        a, b = float(dct[q1]), float(dct[q2])
        avg = (a + b) / 2
        if bit:
            dct[q1], dct[q2] = avg + strength / 2, avg - strength / 2
        else:
            dct[q1], dct[q2] = avg - strength / 2, avg + strength / 2
        y[r:r + block, c:c + block] = cv2.idct(dct)
    ycc[:h8, :w8, 0] = np.clip(y, 0, 255).astype(np.uint8)
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)


def _extract_once(img, n_bits, key, block=8, q1=(3, 4), q2=(4, 3)):
    h, w = img.shape[:2]
    h8, w8 = h - h % block, w - w % block
    _, y = _y(img)
    coords = [(r, c) for r in range(block, h8 - block, block)
              for c in range(block, w8 - block, block)]
    prf_rng(key, "ll01").shuffle(coords)
    votes = [[] for _ in range(n_bits)]
    for idx, (r, c) in enumerate(coords):
        dct = cv2.dct(y[r:r + block, c:c + block])
        votes[idx % n_bits].append(1 if dct[q1] > dct[q2] else 0)
    bits, conf = [], []
    for v in votes:
        m = float(np.mean(v)) if v else 0.5
        bits.append(1 if m >= 0.5 else 0)
        conf.append(abs(m - 0.5) * 2)
    return np.asarray(bits, np.uint8), float(np.mean(conf))


def extract_robust(img, registered_shape, n_bits, key, sync_cfg: RobustConfig):
    """Blind extraction over the shared candidate set, ranked by the
    baseline's own confidence."""
    best = None
    for name, cand in _sync_candidates(img, registered_shape, sync_cfg):
        bits, conf = _extract_once(cand, n_bits, key)
        if best is None or conf > best[1]:
            best = (bits, conf, name)
    return {"bits": best[0], "confidence": best[1], "sync_candidate": best[2],
            "pilot_ber": float("nan"), "present": True}


def _block_bit(block, key):
    gray = cv2.cvtColor((block >> 1).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    payload = bytes([int(np.mean(gray)) & 255, int(np.std(gray)) & 255]) + \
        hashlib.sha256(str(key).encode()).digest()[:4]
    return int(hashlib.sha256(payload).digest()[0] & 1)


def embed_fragile(img, key, block_size=16):
    out = img.copy().astype(np.uint8)
    h, w = out.shape[:2]
    h0, w0 = h - h % block_size, w - w % block_size
    for r in range(0, h0, block_size):
        for c in range(0, w0, block_size):
            bit = _block_bit(out[r:r + block_size, c:c + block_size], key)
            out[r, c, 2] = (out[r, c, 2] & 0xFE) | bit
    return out


def verify_fragile(img, key, block_size=16):
    h, w = img.shape[:2]
    h0, w0 = h - h % block_size, w - w % block_size
    mask = np.zeros((h, w), dtype=np.uint8)
    flagged = total = 0
    for r in range(0, h0, block_size):
        for c in range(0, w0, block_size):
            total += 1
            exp = _block_bit(img[r:r + block_size, c:c + block_size], key)
            if exp != int(img[r, c, 2] & 1):
                mask[r:r + block_size, c:c + block_size] = 255
                flagged += 1
    ratio = flagged / max(1, total)
    status = "tampered" if flagged else "authentic"
    return {"status": status, "tamper_map": mask,
            "median_rho": float("nan"), "flagged_ratio": ratio}
