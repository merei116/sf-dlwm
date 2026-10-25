"""Image IO and dataset utilities.

The benchmark uses real images placed in `data/images/` (e.g., the USC-SIPI
miscellaneous volume; see README for the download command). If that directory
is empty, a deterministic synthetic dataset is generated and the experiment
logs record `dataset=synthetic_demo` so results can never be silently
misattributed to USC-SIPI (a code/paper inconsistency in the original study).
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def read_image_rgb(path, image_size=None):
    img = Image.open(path).convert("RGB")
    if image_size:
        img = img.resize((image_size, image_size), Image.LANCZOS)
    return np.array(img, dtype=np.uint8)


def save_image_rgb(path, img):
    ensure_dir(Path(path).parent)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path)


def list_images(input_dir):
    p = Path(input_dir)
    if not p.exists():
        return []
    return sorted(x for x in p.rglob("*") if x.suffix.lower() in IMG_EXTS)


def generate_demo_dataset(out_dir, n=39, size=512, seed=42):
    """Deterministic synthetic images with smooth, textured and edge content.
    Used ONLY as a fallback when no real dataset is present."""
    ensure_dir(out_dir)
    rng = np.random.default_rng(seed)
    paths = []
    for i in range(n):
        bg = tuple(int(x) for x in rng.integers(20, 235, 3))
        img = Image.new("RGB", (size, size), bg)
        d = ImageDraw.Draw(img)
        for _ in range(int(rng.integers(9, 20))):
            color = tuple(int(x) for x in rng.integers(0, 255, 3))
            x1, y1 = (int(v) for v in rng.integers(0, size - 60, 2))
            x2, y2 = x1 + int(rng.integers(30, 190)), y1 + int(rng.integers(30, 190))
            shape = rng.choice(["rect", "ellipse", "line"])
            wdt = int(rng.integers(2, 7))
            if shape == "rect":
                d.rectangle([x1, y1, min(x2, size), min(y2, size)], outline=color, width=wdt)
            elif shape == "ellipse":
                d.ellipse([x1, y1, min(x2, size), min(y2, size)], outline=color, width=wdt)
            else:
                d.line([x1, y1, min(x2, size), min(y2, size)], fill=color, width=wdt)
        arr = np.array(img).astype(np.int16)
        grad = np.linspace(0, 30, size).astype(np.int16)[None, :, None]
        arr = np.clip(arr + grad + rng.normal(0, 7, arr.shape), 0, 255).astype(np.uint8)
        p = Path(out_dir) / f"demo_{i:03d}.png"
        Image.fromarray(arr).save(p)
        paths.append(p)
    return paths


def resolve_dataset(cfg):
    """Return (image_paths, dataset_name). Prefers real images."""
    real = list_images(cfg["dataset"]["image_dir"])
    n = cfg["dataset"]["n_images"]
    if real:
        return real[:n], Path(cfg["dataset"]["image_dir"]).name
    demo_dir = cfg["dataset"]["demo_dir"]
    paths = list_images(demo_dir) or generate_demo_dataset(
        demo_dir, n=n, size=cfg["dataset"]["image_size"], seed=cfg["seed"])
    return paths[:n], "synthetic_demo"
