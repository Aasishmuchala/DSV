"""Scale calibration: derive mm/px from printed tick marks on the DSV strip/bands."""
from __future__ import annotations

import numpy as np
import cv2
from typing import Optional


# HSV colour ranges for scale ticks (printed black/white lines on adhesive tape)
# Tick detection: invert image → threshold → find vertical lines
HSV_TICK_LOWER = np.array([0, 0, 140])
HSV_TICK_UPPER = np.array([180, 30, 255])


def _detect_tick_positions(img_gray: np.ndarray, x_range: tuple[int, int]) -> list[int]:
    """
    Find the y-positions of scale tick marks in a vertical centre-strip region.

    The strip runs from x_left to x_right. The tick marks are short white lines
    perpendicular to a central vertical tick line. The tick line may be at any
    x within the strip (strip detection isn't always pixel-perfect).
    The tick column is the one with the HIGHEST variance — white on dark = bright.

    Strategy:
      1. Scan every column in the strip and find the one with max brightness variance
         (this is always the tick line, even when strip detection is slightly off).
      2. Sample a 5-px column around it and find rows that are bright (the tick marks).

    Returns sorted list of y-positions (pixel row numbers).
    """
    x0, x1 = x_range
    strip = img_gray[:, x0:x1]
    h, strip_w = strip.shape[:2]

    # Step 1: find the column with the highest brightness variance inside the strip.
    # The tick line (white on dark strip) has maximum local contrast/variance.
    col_vars = np.var(strip, axis=0)  # variance per column
    tick_col_local = int(np.argmax(col_vars))   # 0-indexed within strip
    tick_col_x = x0 + tick_col_local             # global x

    # Step 2: sample a 5-px column around the tick line centre
    col_half = 2
    col_left  = max(0,      tick_col_local - col_half)
    col_right = min(strip_w, tick_col_local + col_half + 1)
    col = strip[:, col_left:col_right].mean(axis=1).astype(float)  # 1-D profile

    # Step 3: ticks are white on the dark strip → rows above threshold are ticks.
    # The strip column has two levels: dark strip (~60) and white tick (~255).
    # Use the 40th percentile as strip baseline; marks are 50% above that.
    strip_level = np.percentile(col, 40)
    threshold   = strip_level + (255 - strip_level) * 0.5

    above = np.where(col > threshold)[0]
    if len(above) == 0:
        return []

    # Step 4: cluster consecutive bright rows into individual tick marks.
    # Each tick spans ~12px vertically; gap between ticks is ~148px at 0.25mm/px.
    # min_sep=20: any gap >20px marks a new tick cluster.
    min_sep = 20
    tick_ys: list[int] = []
    cluster = [above[0]]
    for y in above[1:]:
        if y - cluster[-1] <= min_sep:
            cluster.append(y)
        else:
            tick_ys.append(int(np.mean(cluster)))
            cluster = [y]
    tick_ys.append(int(np.mean(cluster)))   # last cluster

    return sorted(tick_ys)


def detect_ticks_on_strip(img_gray: np.ndarray, strip_rect: tuple[int, int, int, int],
                           tick_spacing_px_hint: Optional[int] = None) -> list[int]:
    """
    Detect tick positions along the centre ruler strip.

    Args:
        img_gray: grayscale image
        strip_rect: (x, y, w, h) of the centre strip region
        tick_spacing_px_hint: if known (from prior detection), helps filter noise

    Returns:
        sorted list of x-positions of tick centers
    """
    x, y, w, h = strip_rect
    x_range = (x, x + w)
    ticks = _detect_tick_positions(img_gray, x_range)
    if tick_spacing_px_hint:
        # Remove outliers: any pair closer than 50% of expected or >150% of expected
        gaps = [ticks[i+1] - ticks[i] for i in range(len(ticks)-1)]
        for i in range(len(gaps)-1, -1, -1):
            if not (tick_spacing_px_hint * 0.5 <= gaps[i] <= tick_spacing_px_hint * 1.5):
                # Remove the tick that creates this bad gap
                if gaps[i] > tick_spacing_px_hint * 1.5:
                    # gap too large: missing tick, keep both
                    pass
                else:
                    # gap too small: noise, remove one
                    ticks.pop(i+1)
    return ticks


def calibrate_scale(ticks: list[int], known_spacing_mm: float) -> float:
    """
    Compute mm_per_px from tick positions.

    Args:
        ticks: sorted list of pixel x-positions of adjacent tick centers
        known_spacing_mm: known mm between adjacent ticks (40mm for centre strip,
                         25mm for band strips)

    Returns:
        mm_per_px (a single scalar)

    Raises:
        ValueError if fewer than 2 ticks or degenerate spacing
    """
    if len(ticks) < 2:
        raise ValueError(f"Need at least 2 ticks for calibration, got {len(ticks)}")

    # Compute pixel spacing for each adjacent pair
    spacings = [ticks[i+1] - ticks[i] for i in range(len(ticks)-1)]
    if not spacings:
        raise ValueError("No adjacent tick pairs")

    # Use median to be robust to any outlier detection
    median_px = float(np.median(spacings))
    if median_px <= 0:
        raise ValueError(f"Degenerate tick spacing: {spacings}")

    mm_per_px = known_spacing_mm / median_px
    return mm_per_px


def calibrate_scale_from_strip(img_gray: np.ndarray,
                                strip_x: int, strip_y: int, strip_w: int, strip_h: int,
                                known_spacing_mm: float,
                                tick_spacing_px_hint: Optional[int] = None) -> float:
    """
    One-shot: find ticks on centre strip and return mm_per_px.
    Fails loudly (raises) if ticks not reliably detected.

    Strategy: look at a WIDER x window than the detected strip (add strip_w on each side).
    The strip_rect from detect_scale_region captures the narrow ruler base, but the
    tick marks protrude slightly beyond it. Expanding the search window ensures we
    capture the full tick column.
    """
    # Expand the search window by strip_w on each side to capture the tick marks
    wide_x = max(0, strip_x - strip_w)
    wide_w = strip_w + strip_w * 2
    ticks = detect_ticks_on_strip(img_gray, (wide_x, strip_y, wide_w, strip_h),
                                    tick_spacing_px_hint)
    return calibrate_scale(ticks, known_spacing_mm)


def detect_scale_region(img_gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    Auto-detect the centre ruler strip region in the image.

    Strategy: find the column with the highest vertical edge density (the tick line).
    The tick line is a single vertical column where the white tick marks cross the strip.
    Expand symmetrically by EXPAND_PX on each side to capture the full strip width.

    Returns (x, y, w, h) or None if not found.
    """
    h, w = img_gray.shape[:2]

    # Vertical edge density per column
    sobelx = cv2.Sobel(img_gray, cv2.CV_64F, 1, 0, ksize=3)
    col_edges = np.abs(sobelx).sum(axis=0)  # shape: (w,)

    # Find the column with maximum edge density (the tick line centre)
    tick_col = int(np.argmax(col_edges))
    peak_density = col_edges[tick_col]
    if peak_density < 1000:   # very faint strip
        return None

    # The tick line is 1-2px wide; the strip (black with white ticks) extends further.
    # At typical ~2000px images, the strip is ~80px. Expand symmetrically.
    EXPAND_PX = max(40, w // 20)   # ~40px at 800w, ~100px at 2000w
    x_left  = max(0,       tick_col - EXPAND_PX)
    x_right = min(w - 1,  tick_col + EXPAND_PX)

    # Require a minimum width (strip must be at least 30px)
    if x_right - x_left < 30:
        return None

    return (x_left, 0, x_right - x_left, h)