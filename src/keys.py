"""Key management and pseudo-random functions (PRF).

All key-dependent randomness in the framework is derived from a single secret
key K through BLAKE2s in keyed mode. This gives:
  * deterministic, reproducible schedules given (key, context),
  * domain separation between the robust layer, the pilot sequence, and the
    per-block authentication masks,
  * no reliance on Python's global RNG state.
"""
import hashlib
import numpy as np


def _key_bytes(key) -> bytes:
    if isinstance(key, bytes):
        return key
    return hashlib.sha256(str(key).encode("utf-8")).digest()


def prf_digest(key, *context, digest_size: int = 32) -> bytes:
    """Keyed BLAKE2s over a domain-separated context tuple."""
    h = hashlib.blake2s(key=_key_bytes(key)[:32], digest_size=digest_size)
    for item in context:
        h.update(b"|")
        h.update(str(item).encode("utf-8"))
    return h.digest()


def prf_bits(key, *context, n_bits: int) -> np.ndarray:
    """n_bits pseudo-random bits derived from (key, context)."""
    out = np.zeros(0, dtype=np.uint8)
    counter = 0
    while out.size < n_bits:
        d = prf_digest(key, *context, "ctr", counter)
        out = np.concatenate([out, np.unpackbits(np.frombuffer(d, dtype=np.uint8))])
        counter += 1
    return out[:n_bits].astype(np.uint8)


def prf_rng(key, *context) -> np.random.Generator:
    """A numpy Generator seeded from (key, context)."""
    seed = int.from_bytes(prf_digest(key, *context, digest_size=8), "big")
    return np.random.default_rng(seed)


def content_id_to_bits(content_id: str, n_bits: int = 64) -> np.ndarray:
    """Map a ContentID string to a fixed-length binary payload.

    Uses the raw BLAKE2b digest bits (a standard collision-resistant mapping),
    not a PRNG expansion, so the payload is a cryptographic fingerprint of the
    identifier.
    """
    n_bytes = (n_bits + 7) // 8
    d = hashlib.blake2b(content_id.encode("utf-8"), digest_size=max(8, n_bytes)).digest()
    return np.unpackbits(np.frombuffer(d, dtype=np.uint8))[:n_bits].astype(np.uint8)
