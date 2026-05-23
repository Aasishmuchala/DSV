"""EXIF-preserving image ingest with HEIC conversion and resize."""
from __future__ import annotations

import io, pathlib, struct, zlib
from typing import Optional

import cv2
import numpy as np

# HEIC support via pillow-heif (install: pip install pillow-heif)
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:
    _HEIF_AVAILABLE = False


def _read_exif_orientation(path: pathlib.Path) -> int:
    """Read EXIF Orientation tag (tag 0x0112 = 274). Returns 1 if not found."""
    try:
        import piexif
        exif = piexif.load(str(path))
        orientation = exif.get("0th", {}).get(piexif.ImageIFD.Orientation, 1)
        return int(orientation)
    except Exception:
        return 1


def _apply_orientation(img: np.ndarray, orientation: int) -> np.ndarray:
    """Rotate/flip image according to EXIF orientation tag."""
    if orientation == 1:
        return img
    transforms = {
        2: lambda m: cv2.flip(m, 1),
        3: lambda m: cv2.flip(m, -1),
        4: lambda m: cv2.flip(m, 0),
        5: lambda m: cv2.transpose(m),
        6: lambda m: cv2.rotate(m, cv2.ROTATE_90_COUNTERCLOCKWISE),
        7: lambda m: cv2.flip(cv2.transpose(m), 1),
        8: lambda m: cv2.rotate(m, cv2.ROTATE_90_CLOCKWISE),
    }
    t = transforms.get(orientation)
    return t(img) if t else img


def _heic_to_array(path: pathlib.Path) -> Optional[np.ndarray]:
    """Convert HEIC to BGR numpy array. Returns None if unavailable."""
    if not _HEIF_AVAILABLE:
        return None
    try:
        from PIL import Image
        img = Image.open(str(path))
        rgb = img.convert("RGB")
        arr = np.asarray(rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def load_image(path: pathlib.Path, max_long_edge: int = 2000) -> tuple[np.ndarray, float]:
    """
    Load an image file (JPG, PNG, HEIC) preserving EXIF orientation.

    Returns:
        (image, scale_factor) — image is BGR, scale_factor is px-to-original ratio.
        A pixel at (x, y) in the returned image maps to (x/scale, y/scale) in original.
    """
    path = pathlib.Path(path)
    ext = path.suffix.lower()

    # --- Load raw bytes ---
    if ext in (".heic", ".heif") and _HEIF_AVAILABLE:
        raw = _heic_to_array(path)
        if raw is None:
            raise RuntimeError(f"HEIC load failed for {path}")
    else:
        raw = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if raw is None:
            raise RuntimeError(f"cv2.imread failed for {path}")

    # --- EXIF orientation ---
    orient = _read_exif_orientation(path)
    if orient != 1:
        raw = _apply_orientation(raw, orient)

    # --- Resize ---
    h, w = raw.shape[:2]
    long_edge = max(h, w)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        raw = cv2.resize(raw, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    else:
        scale = 1.0

    return raw, scale


def load_image_pair(front_path: pathlib.Path, side_path: pathlib.Path,
                    max_long_edge: int = 2000) -> tuple[tuple[np.ndarray, float], tuple[np.ndarray, float]]:
    """Convenience: load front + side images together."""
    front = load_image(front_path, max_long_edge)
    side = load_image(side_path, max_long_edge)
    return front, side