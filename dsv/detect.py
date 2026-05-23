"""HSV colour segmentation for DSV marker detection (neon green default)."""
from __future__ import annotations

import numpy as np
import cv2
from typing import Optional

# HSV colour ranges for DSV marker detection (neon green default)
HSV_GREEN = ((36, 100, 70), (85, 255, 255))
HSV_CYAN  = ((90, 100, 70), (140, 255, 255))
HSV_RED   = ((0, 120, 90),  (10, 255, 255))   # wrap-around hue
HSV_RED2  = ((170, 120, 90), (180, 255, 255))
# Monochrome fallback: high S + high V, ignores hue
HSV_FALLBACK_SAT = 150
HSV_FALLBACK_VAL = 100

# Contour filtering params
MIN_MARKER_AREA = 60    # px²
MAX_MARKER_AREA = 3000  # px²
MIN_CIRCULARITY = 0.55

# Marker diameter in mm
MARKER_DIAM_MM = 16


def _in_range(val: int, lo: int, hi: int) -> bool:
    return lo <= val <= hi


def _in_hsv_range(pixel: np.ndarray, lower: tuple[int,int,int], upper: tuple[int,int,int]) -> bool:
    h, s, v = pixel
    lh, ls, lv = lower
    uh, us, uv = upper
    # Hue wraps around 180 in OpenCV
    if lh <= uh:
        in_hue = lh <= h <= uh
    else:
        in_hue = h >= lh or h <= uh
    return in_hue and ls <= s <= us and lv <= v <= uv


def segment_colour(img_bgr: np.ndarray, hsv_ranges: list[tuple[tuple[int,int,int], tuple[int,int,int]]]) -> np.ndarray:
    """
    Create a binary mask where pixels are in any of the given HSV ranges.
    img_bgr: BGR image from cv2.imread
    hsv_ranges: list of (lower, upper) HSV tuples
    Returns: 8-bit binary mask (255 = marker pixel)
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in hsv_ranges:
        lo = np.array(lower, dtype=np.uint8)
        up = np.array(upper, dtype=np.uint8)
        m = cv2.inRange(hsv, lo, up)
        mask = cv2.bitwise_or(mask, m)
    return mask


def segment_green(img_bgr: np.ndarray) -> np.ndarray:
    return segment_colour(img_bgr, [HSV_GREEN])


def segment_cyan(img_bgr: np.ndarray) -> np.ndarray:
    return segment_colour(img_bgr, [HSV_CYAN])


def segment_red(img_bgr: np.ndarray) -> np.ndarray:
    return segment_colour(img_bgr, [HSV_RED, HSV_RED2])


def segment_fallback(img_bgr: np.ndarray) -> np.ndarray:
    """High-saturation monochrome: ignore hue, keep only vivid pixels."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,
                        np.array([0, HSV_FALLBACK_SAT, HSV_FALLBACK_VAL], dtype=np.uint8),
                        np.array([180, 255, 255], dtype=np.uint8))
    return mask


def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Morphological open + close to remove noise and fill gaps."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def _circularity(contour: np.ndarray) -> float:
    """Circularity = 4π·Area / Perimeter². 1.0 = perfect circle."""
    area = cv2.contourArea(contour)
    if area < 1:
        return 0.0
    perimeter = cv2.arcLength(contour, True)
    if perimeter < 1:
        return 0.0
    return (4 * np.pi * area) / (perimeter * perimeter)


def find_markers(mask: np.ndarray) -> list[dict]:
    """
    Find marker blobs in a binary mask using contour analysis.

    Returns:
        List of dicts with keys: cx (x center), cy (y center), r (radius px),
        area (px²), circularity (0-1)
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    markers = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MIN_MARKER_AREA <= area <= MAX_MARKER_AREA):
            continue
        circ = _circularity(cnt)
        if circ < MIN_CIRCULARITY:
            continue
        # Bounding circle
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        markers.append({
            "cx": int(cx),
            "cy": int(cy),
            "r": float(r),
            "area": float(area),
            "circularity": circ,
        })
    return markers


def detect_markers_auto(img_bgr: np.ndarray) -> tuple[list[dict], str]:
    """
    Try each colour strategy in order. Return (markers, colour_used).
    colour_used: 'green', 'cyan', 'red', 'fallback', or 'none'
    """
    for colour, fn in [
        ("green",   segment_green),
        ("cyan",    segment_cyan),
        ("red",     segment_red),
        ("fallback", segment_fallback),
    ]:
        mask = fn(img_bgr)
        mask = clean_mask(mask)
        markers = find_markers(mask)
        if len(markers) >= 4:  # at least shoulder row minimum
            return markers, colour
    return [], "none"


def detect_markers(img_bgr: np.ndarray, colour: str = "green") -> tuple[list[dict], str]:
    """Detect markers with a specific colour strategy."""
    strategies = {
        "green":   (segment_green,   "green"),
        "cyan":    (segment_cyan,    "cyan"),
        "red":     (segment_red,     "red"),
        "fallback": (segment_fallback, "fallback"),
    }
    if colour not in strategies:
        raise ValueError(f"Unknown colour: {colour}. Available: {list(strategies.keys())}")
    fn, label = strategies[colour]
    mask = clean_mask(fn(img_bgr))
    markers = find_markers(mask)
    return markers, label