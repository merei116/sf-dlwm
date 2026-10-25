"""Error-correcting code for the robust payload.

A rate-1/r repetition code with key-dependent interleaving and soft-decision
decoding. Repetition is deliberately chosen over BCH/LDPC to keep the layer
dependency-free and fully transparent; the ablation study quantifies its
contribution (ecc.rate=1 disables it).

Soft decoding: each coded bit position accumulates a real-valued score from
the channel (sum of carrier margins). The decoder sums the scores of the r
repetitions of each payload bit and takes the sign, which is the ML decision
for a binary-input AWGN-like channel.
"""
import numpy as np
from .keys import prf_rng


def encode(bits: np.ndarray, rate: int, key, tag: str = "ecc") -> np.ndarray:
    """Repeat each payload bit `rate` times and interleave with a key-dependent
    permutation. Returns the coded bit sequence."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    coded = np.repeat(bits, rate)
    perm = prf_rng(key, tag, len(coded)).permutation(len(coded))
    return coded[perm]


def decode_soft(scores: np.ndarray, n_payload: int, rate: int, key, tag: str = "ecc"):
    """Soft-decision decode. `scores[i]` is the accumulated channel score of
    coded position i (positive => bit 1). Returns (bits, per-bit confidence)."""
    scores = np.asarray(scores, dtype=np.float64).ravel()
    n_coded = n_payload * rate
    perm = prf_rng(key, tag, n_coded).permutation(n_coded)
    deinter = np.zeros(n_coded, dtype=np.float64)
    deinter[perm] = scores[:n_coded]
    grouped = deinter.reshape(n_payload, rate).sum(axis=1)
    bits = (grouped >= 0).astype(np.uint8)
    conf = np.abs(grouped)
    return bits, conf
