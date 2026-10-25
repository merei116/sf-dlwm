"""Perceptual-hash baseline for the content-identification task.

pHash carries no payload; identification succeeds when the Hamming distance
between the received image's hash and the registered hash is below a
threshold. It is included as a non-watermark reference point for the
"can the verifier re-identify this image?" question.
"""
import numpy as np
import cv2


def phash(img, hash_size=8, highfreq_factor=4):
    img_size = hash_size * highfreq_factor
    gray = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (img_size, img_size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(small))
    low = dct[:hash_size, :hash_size]
    med = np.median(low[1:, 1:])
    return (low > med).astype(np.uint8).ravel()


def identify(attacked, registered_hash, threshold_bits=10):
    h = phash(attacked)
    n = min(len(h), len(registered_hash))
    dist = int(np.sum(h[:n] != registered_hash[:n]))
    return {"hamming": dist, "detected": dist <= threshold_bits,
            "ber": dist / max(1, n)}
