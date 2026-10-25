"""Evaluation metrics: BER, NC, PSNR, SSIM, and mask metrics
(precision, recall/TPR, FPR, F1/Dice, IoU)."""
import numpy as np
from math import comb
from skimage.metrics import structural_similarity as ssim


def psnr(a, b):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    mse = float(np.mean((a - b) ** 2))
    if mse == 0:
        return float("inf")
    return float(20 * np.log10(255.0 / np.sqrt(mse)))


def ssim_rgb(a, b):
    return float(ssim(a.astype(np.uint8), b.astype(np.uint8),
                      channel_axis=2, data_range=255))


def bit_error_rate(a, b):
    a = np.asarray(a, np.uint8).ravel()
    b = np.asarray(b, np.uint8).ravel()
    n = min(len(a), len(b))
    return 1.0 if n == 0 else float(np.mean(a[:n] != b[:n]))


def normalized_correlation(a, b):
    a = 2.0 * np.asarray(a, np.float64).ravel() - 1.0
    b = 2.0 * np.asarray(b, np.float64).ravel() - 1.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    denom = np.linalg.norm(a[:n]) * np.linalg.norm(b[:n])
    return 0.0 if denom == 0 else float(np.dot(a[:n], b[:n]) / denom)


def mask_metrics(pred, gt):
    """Pixel-level localization metrics. Dice == F1 for binary masks."""
    pred = np.asarray(pred).astype(bool)
    gt = np.asarray(gt).astype(bool)
    tp = float(np.logical_and(pred, gt).sum())
    fp = float(np.logical_and(pred, ~gt).sum())
    fn = float(np.logical_and(~pred, gt).sum())
    tn = float(np.logical_and(~pred, ~gt).sum())
    precision = tp / (tp + fp + 1e-9)
    recall = tp / (tp + fn + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    iou = tp / (tp + fp + fn + 1e-9)
    fpr = fp / (fp + tn + 1e-9)
    return {"tamper_precision": precision, "tamper_recall": recall,
            "tamper_tpr": recall, "tamper_fpr": fpr,
            "tamper_f1": f1, "tamper_dice": f1, "tamper_iou": iou,
            "predicted_positive_rate": float(pred.mean())}


def random_payload_false_alarm(n_bits, tau_ber):
    """Analytic probability that an L-bit random payload passes BER <= tau
    against a fixed registered payload (binomial tail, p = 0.5)."""
    k_max = int(np.floor(tau_ber * n_bits))
    return sum(comb(n_bits, k) for k in range(k_max + 1)) / 2.0 ** n_bits
