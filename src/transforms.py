"""Benign transformations and tampering attacks.

Every scenario returns (image, ground_truth_mask_or_None). Fixes relative to
the original codebase:
  * inpainting-like attack no longer Gaussian-blurs the ENTIRE image (which
    made the attack a global filter and invalidated the localization ground
    truth); smoothing is confined to the edited region;
  * tamper attacks are optionally followed by a mild JPEG re-encode
    ("*_jpeg85" scenarios) to test localization under realistic conditions;
  * copy-move ground truth marks the destination region (stated explicitly:
    the source region is unchanged content and is NOT counted as tampered).
"""
import numpy as np
import cv2
from io import BytesIO
from PIL import Image


def jpeg_compress(img, quality=85):
    buf = BytesIO()
    Image.fromarray(img.astype(np.uint8)).save(buf, format="JPEG",
                                               quality=int(quality), optimize=True)
    buf.seek(0)
    return np.array(Image.open(buf).convert("RGB"), dtype=np.uint8)


def resize_scale(img, scale=0.75):
    h, w = img.shape[:2]
    nw, nh = max(8, int(w * scale)), max(8, int(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    small = cv2.resize(img, (nw, nh), interpolation=interp)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def blur(img, k=3):
    return cv2.GaussianBlur(img, (k, k), 0)


def add_noise(img, sigma=8, seed=42):
    rng = np.random.default_rng(seed)
    return np.clip(img.astype(np.float32) + rng.normal(0, sigma, img.shape),
                   0, 255).astype(np.uint8)


def center_crop_resize(img, crop_ratio=0.85):
    h, w = img.shape[:2]
    ch, cw = int(h * crop_ratio), int(w * crop_ratio)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    return cv2.resize(img[y0:y0 + ch, x0:x0 + cw], (w, h),
                      interpolation=cv2.INTER_CUBIC)


def rotate(img, angle=5):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REFLECT)


def copy_move_attack(img, seed=42, frac=5):
    """Copy a region to a different location. GT marks the DESTINATION."""
    rng = np.random.default_rng(seed)
    out = img.copy()
    h, w = img.shape[:2]
    bh, bw = h // frac, w // frac
    while True:
        y1, x1 = int(rng.integers(0, h - bh)), int(rng.integers(0, w - bw))
        y2, x2 = int(rng.integers(0, h - bh)), int(rng.integers(0, w - bw))
        if abs(y1 - y2) > bh // 2 or abs(x1 - x2) > bw // 2:
            break
    out[y2:y2 + bh, x2:x2 + bw] = img[y1:y1 + bh, x1:x1 + bw]
    gt = np.zeros((h, w), dtype=np.uint8)
    gt[y2:y2 + bh, x2:x2 + bw] = 255
    return out, gt


def inpainting_like_attack(img, seed=42):
    """Replace a region by its median color and smooth ONLY that region."""
    rng = np.random.default_rng(seed)
    out = img.copy()
    h, w = img.shape[:2]
    mh, mw = h // 5, w // 4
    y = int(rng.integers(h // 5, h - mh))
    x = int(rng.integers(w // 5, w - mw))
    color = np.median(out[y:y + mh, x:x + mw].reshape(-1, 3), axis=0)
    out[y:y + mh, x:x + mw] = color
    region = out[max(0, y - 4):y + mh + 4, max(0, x - 4):x + mw + 4]
    out[max(0, y - 4):y + mh + 4, max(0, x - 4):x + mw + 4] = \
        cv2.GaussianBlur(region, (7, 7), 0)
    gt = np.zeros((h, w), dtype=np.uint8)
    gt[y:y + mh, x:x + mw] = 255
    return out.astype(np.uint8), gt


def platform_telegram_like(img):
    return jpeg_compress(img, 85)


def platform_whatsapp_like(img):
    return jpeg_compress(resize_scale(img, 0.75), 65)


def platform_instagram_like(img):
    h, w = img.shape[:2]
    s = min(h, w)
    y, x = (h - s) // 2, (w - s) // 2
    sq = cv2.resize(img[y:y + s, x:x + s], (w, h), interpolation=cv2.INTER_CUBIC)
    return jpeg_compress(sq, 82)


# scenario registry ---------------------------------------------------------

BENIGN = ["identity", "jpeg95", "jpeg85", "jpeg70", "jpeg50", "jpeg30",
          "resize090", "resize075", "resize050", "blur3", "noise8",
          "crop_center", "rotate5",
          "telegram_like", "whatsapp_like", "instagram_like",
          "mixed_instagram_crop_jpeg"]
TAMPER = ["copy_move", "inpaint_like", "copy_move_jpeg85", "inpaint_like_jpeg85"]
ALL_SCENARIOS = BENIGN + TAMPER


def apply_transform(name, img, seed=42):
    if name == "identity":
        return img.copy(), None
    if name.startswith("jpeg"):
        return jpeg_compress(img, int(name[4:])), None
    if name == "resize090":
        return resize_scale(img, 0.90), None
    if name == "resize075":
        return resize_scale(img, 0.75), None
    if name == "resize050":
        return resize_scale(img, 0.50), None
    if name == "blur3":
        return blur(img, 3), None
    if name == "noise8":
        return add_noise(img, 8, seed), None
    if name == "crop_center":
        return center_crop_resize(img, 0.85), None
    if name == "rotate5":
        return rotate(img, 5), None
    if name == "telegram_like":
        return platform_telegram_like(img), None
    if name == "whatsapp_like":
        return platform_whatsapp_like(img), None
    if name == "instagram_like":
        return platform_instagram_like(img), None
    if name == "mixed_instagram_crop_jpeg":
        x = platform_instagram_like(img)
        x = center_crop_resize(x, 0.90)
        return jpeg_compress(x, 70), None
    if name == "copy_move":
        return copy_move_attack(img, seed)
    if name == "inpaint_like":
        return inpainting_like_attack(img, seed)
    if name == "copy_move_jpeg85":
        out, gt = copy_move_attack(img, seed)
        return jpeg_compress(out, 85), gt
    if name == "inpaint_like_jpeg85":
        out, gt = inpainting_like_attack(img, seed)
        return jpeg_compress(out, 85), gt
    raise ValueError(f"unknown scenario: {name}")
