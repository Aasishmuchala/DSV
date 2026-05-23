"""Robust geometric labelling — maps marker centroids to body landmark names.

Stress-tested against:
  - Slouch (HPS drops below shoulder tips in image y)
  - Missing markers
  - Level mismatches between front and side views
  - Body landmark → x-position relationships are used over y-order
"""
from __future__ import annotations

import numpy as np
from typing import Optional
from dataclasses import dataclass, field

from .detect import MARKER_DIAM_MM

# Pixel tolerance for same-level check (at typical ~2000px long edge)
LEVEL_TOLERANCE_PX = 20

# How far from x-midline to consider a marker as a centre-front marker (in marker diameters)
# 0.8 × diameter = 38px threshold — HPS markers at ~60px from x_mid are NOT midline,
# so they appear in side_left/right and get included in the shoulder row detection.
MIDLINE_THRESH_DIAM = 0.8


@dataclass
class LabelResult:
    """Labelling output with confidence metadata."""
    labels: dict[str, tuple[int, int]]  # name → (cx, cy) pixel coords
    flags: list[str]                    # MISSING_MARKER, LEVEL_MISMATCH, etc.
    warnings: list[str]
    colour_used: str = "unknown"
    side_labels: dict[str, tuple[int, int]] = field(default_factory=dict)
    side_flags: list[str] = field(default_factory=list)
    side_warnings: list[str] = field(default_factory=list)


def _midline_distance(cx: int, x_mid: int) -> float:
    return abs(cx - x_mid)


def _diam_to_px(diam_mm: float, mm_per_px: float) -> int:
    return int(diam_mm / mm_per_px)


def _sort_by_x(markers: list[dict]) -> list[dict]:
    return sorted(markers, key=lambda m: m["cx"])


def _sort_by_y(markers: list[dict]) -> list[dict]:
    return sorted(markers, key=lambda m: m["cy"])


def _y_spread(markers: list[dict]) -> int:
    if not markers:
        return 0
    ys = [m["cy"] for m in markers]
    return max(ys) - min(ys)


def _x_distance(a: dict, b: dict) -> float:
    return abs(a["cx"] - b["cx"])


def _y_distance(a: dict, b: dict) -> float:
    return abs(a["cy"] - b["cy"])


def _avg_y(markers: list[dict]) -> float:
    return np.mean([m["cy"] for m in markers])


# ---------------------------------------------------------------------------
# Front view labelling
# ---------------------------------------------------------------------------

def label_front(markers: list[dict], x_mid: int, marker_diam_px: int,
                mm_per_px: float, img_h: int = 1200) -> LabelResult:
    """
    Label front-view markers.

    Args:
        markers: list of marker dicts with cx, cy, r
        x_mid: x-coordinate of the image centerline (where cf markers sit)
        marker_diam_px: marker diameter in pixels (for thresholding)
        mm_per_px: for unit conversion in diagnostics
    """
    result = LabelResult(labels={}, flags=[], warnings=[])
    md_thresh_px = int(MIDLINE_THRESH_DIAM * marker_diam_px)

    markers = list(markers)  # don't mutate input

    # --- Step 1: split into midline vs side ---
    midline_markers = [m for m in markers if _midline_distance(m["cx"], x_mid) <= md_thresh_px]
    side_markers    = [m for m in markers if _midline_distance(m["cx"], x_mid) >  md_thresh_px]

    # Sort side markers left/right
    side_left  = sorted([m for m in side_markers if m["cx"] < x_mid], key=lambda m: m["cx"])
    side_right = sorted([m for m in side_markers if m["cx"] >= x_mid], key=lambda m: m["cx"])

    # Sort all markers by y to understand vertical layout
    all_by_y = _sort_by_y(markers)
    if len(all_by_y) < 4:
        result.warnings.append(f"Only {len(markers)} markers detected — labelling will be incomplete")
        # Still try
        for m in markers:
            result.labels[f"marker_{m['cx']}_{m['cy']}"] = (m["cx"], m["cy"])
        return result

    # --- Step 2: Identify shoulder row ---
    # The shoulder row is the top-most cluster of markers in the upper body.
    # Use x-extremes to separate from HPS (HPS is near midline, shoulder tips are far left/right).
    # Shoulder tips are at the far left/right of the shoulder row.
    # HPS markers are near x_mid.

    # Get markers in the top portion of the image (shoulder/neck region).
    # Use the TOP 2 side markers (most extreme y) to define the cutoff —
    # this avoids midline markers (cf_neck at y=200) from inflating the cutoff
    # and accidentally being included in the shoulder row.
    side_by_y = sorted(side_left + side_right, key=lambda m: m["cy"])
    if len(side_by_y) >= 2:
        # Bottom of the top-2 side markers = the shoulder tip row
        shoulder_bottom = side_by_y[1]["cy"]
        top_cutoff = shoulder_bottom + marker_diam_px
    elif side_by_y:
        top_cutoff = side_by_y[0]["cy"] + marker_diam_px
    else:
        top_cutoff = img_h * 0.4

    top_markers = [m for m in markers if m["cy"] <= top_cutoff]

    # Within top markers, shoulder tips = most extreme x positions
    # HPS = closest to x_mid
    top_by_x = _sort_by_x(top_markers)

    if len(top_by_x) >= 4:
        shoulder_row = top_by_x[:4]
        # Map: leftmost = sh_tip_L, next = hps_L, next = hps_R, rightmost = sh_tip_R
        result.labels["sh_tip_L"] = (shoulder_row[0]["cx"], shoulder_row[0]["cy"])
        result.labels["sh_tip_R"] = (shoulder_row[-1]["cx"], shoulder_row[-1]["cy"])
        result.labels["hps_L"]    = (shoulder_row[1]["cx"], shoulder_row[1]["cy"])
        result.labels["hps_R"]    = (shoulder_row[2]["cx"], shoulder_row[2]["cy"])

    elif len(top_by_x) == 3:
        # Only 3 markers in the shoulder row — one shoulder tip is missing.
        result.flags.append("MISSING_MARKER: shoulder_row (got 3, need 4)")
        result.warnings.append("One shoulder tip missing — across_shoulder will be incomplete")
        # Assign what we have: extremes as shoulder tips, inner as HPS pair
        result.labels["sh_tip_L"] = (top_by_x[0]["cx"], top_by_x[0]["cy"])
        result.labels["sh_tip_R"] = (top_by_x[-1]["cx"], top_by_x[-1]["cy"])
        result.labels["hps_L"]    = (top_by_x[1]["cx"], top_by_x[1]["cy"])

    elif len(top_by_x) < 3:
        result.flags.append("MISSING_MARKER: shoulder_row (got fewer than 3)")
        result.warnings.append(f"Too few markers in shoulder region ({len(top_by_x)}) — labelling degraded")

    # --- Step 3: Centre-front markers (cf_neck, cf_underbust, cf_waist, cf_hip) ---
    # These are the midline markers, one per band
    for name, mid_m in zip(["cf_neck", "cf_underbust", "cf_waist", "cf_hip"],
                           midline_markers[:4]):
        result.labels[name] = (mid_m["cx"], mid_m["cy"])

    # Validate cf_neck position: must be between shoulder row and bust
    if "cf_neck" in result.labels and "hps_R" in result.labels and "bust_L" in result.labels:
        cf_y = result.labels["cf_neck"][1]
        hps_y = result.labels["hps_R"][1]
        bust_y = result.labels["bust_L"][1]
        if not (hps_y <= cf_y <= bust_y + marker_diam_px * 2):
            result.flags.append("LABEL_UNCERTAIN: cf_neck outside expected vertical range")
            result.warnings.append(f"cf_neck y={cf_y} not between hps_y={hps_y} and bust_y={bust_y}")

    # --- Step 4: Side pair markers ---
    # For each body level (bust, underbust, waist, hip), there are left + right markers
    # They are the leftmost + rightmost non-midline markers at each y-band

    # Group side markers by vertical band
    def y_band(m: dict, step: int) -> int:
        return m["cy"] // step

    band_step = marker_diam_px * 3  # approximate band height in pixels
    bands: dict[int, list[dict]] = {}
    for m in side_left + side_right:
        band = y_band(m, band_step)
        bands.setdefault(band, []).append(m)

    # Map from band to level name — based on expected y ordering (top to bottom)
    # shoulder row is top, then bust, underbust, waist, hip
    sorted_bands = sorted(bands.keys())
    level_names = ["bust", "underbust", "waist", "hip"]
    band_to_level = {}
    if sorted_bands:
        # Distribute bands to level names (skip shoulder bands)
        # Shoulder row already labelled — focus on the band markers
        for i, band in enumerate(sorted_bands[-4:]):  # bottom 4 bands
            if i < len(level_names):
                band_to_level[band] = level_names[i]

    for band, level in band_to_level.items():
        bm = bands[band]
        leftmost  = min(bm, key=lambda m: m["cx"])
        rightmost = max(bm, key=lambda m: m["cx"])
        result.labels[f"{level}_L"] = (leftmost["cx"], leftmost["cy"])
        result.labels[f"{level}_R"] = (rightmost["cx"], rightmost["cy"])

    # --- Step 5: Level mismatch check ---
    # For each band level, front L and R should be at similar y
    for level in level_names:
        l_key = f"{level}_L"
        r_key = f"{level}_R"
        if l_key in result.labels and r_key in result.labels:
            ly = result.labels[l_key][1]
            ry = result.labels[r_key][1]
            if abs(ly - ry) > LEVEL_TOLERANCE_PX:
                result.flags.append(f"LEVEL_MISMATCH: {level} (|y_L - y_R| = {abs(ly-ry)}px)")
                result.warnings.append(f"{level} markers have y-spread of {abs(ly-ry)}px (threshold {LEVEL_TOLERANCE_PX}px)")

    return result


# ---------------------------------------------------------------------------
# Side view labelling
# ---------------------------------------------------------------------------

def label_side(markers: list[dict], mm_per_px: float) -> LabelResult:
    """
    Label side-view markers.

    Side view has markers: sh_tip_side, bust_side, underbust_side, waist_side, hip_side
    Sorted by y (top to bottom).
    """
    result = LabelResult(labels={}, flags=[], warnings=[], side_labels={}, side_flags=[], side_warnings=[])
    markers = _sort_by_y(list(markers))  # sort top to bottom

    if len(markers) == 0:
        result.side_flags.append("NO_MARKERS: side view")
        return result

    # Sanity check: y-span must be at least 200px for a human torso
    y_span = _y_spread(markers)
    if y_span < 200:
        result.side_flags.append("SIDE_VIEW_INVALID: y_span_too_narrow ({y_span}px)")
        result.side_warnings.append(f"Side view y-span only {y_span}px — expected at least 200px for a human torso")

    expected_names = ["sh_tip_side", "bust_side", "underbust_side", "waist_side", "hip_side"]
    expected_count = len(expected_names)

    # Map sorted markers to expected names by y-position
    if len(markers) == expected_count:
        for name, m in zip(expected_names, markers):
            result.side_labels[name] = (m["cx"], m["cy"])
    elif len(markers) > 0 and len(markers) < expected_count:
        # Missing some — flag and map what we can
        result.side_flags.append(f"MISSING_MARKER: side_row (got {len(markers)}, need {expected_count})")
        # Map top marker to sh_tip_side, bottom to hip_side, distribute the rest
        for i, m in enumerate(markers):
            frac = i / max(len(markers) - 1, 1)
            idx = int(frac * (expected_count - 1))
            result.side_labels[expected_names[idx]] = (m["cx"], m["cy"])
        result.side_warnings.append(f"Only {len(markers)} side markers — mapping may be incorrect")
    else:
        # More markers than expected — just label top/bottom extremes and warn
        result.side_flags.append(f"EXTRA_MARKERS: side_row (got {len(markers)}, expected {expected_count})")
        if markers:
            result.side_labels["sh_tip_side"] = (markers[0]["cx"], markers[0]["cy"])
            result.side_labels["hip_side"]    = (markers[-1]["cx"], markers[-1]["cy"])
        result.side_warnings.append("More side markers than expected — verify labelling")

    return result


def cross_validate_levels(front_result: LabelResult, side_result: LabelResult,
                           level_tolerance_px: int = LEVEL_TOLERANCE_PX) -> LabelResult:
    """
    Cross-validate front vs side y positions for each body level.
    Updates front_result with side_validation flags.
    """
    level_names = ["bust", "underbust", "waist", "hip"]

    for level in level_names:
        f_key = f"{level}_L"  # use front _L as reference
        s_key = f"{level}_side"

        if f_key not in front_result.labels or s_key not in side_result.side_labels:
            continue

        fy = front_result.labels[f_key][1]
        sy = side_result.side_labels[s_key][1]

        delta = abs(fy - sy)
        if delta > level_tolerance_px:
            flag = f"LEVEL_MISMATCH: {level}_front_vs_side (Δy={delta}px)"
            front_result.flags.append(flag)
            front_result.warnings.append(
                f"{level}: front y={fy}, side y={sy}, Δ={delta}px (threshold {level_tolerance_px}px)"
            )

    return front_result