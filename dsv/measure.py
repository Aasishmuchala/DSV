"""Measurement computation: linear distances, angles, and Ramanujan ellipse girths."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Measurement:
    value: float          # mm
    confidence: str        # "high", "med", "low"
    human_read_mm: Optional[float] = None
    app_read_mm: Optional[float] = None
    agree: Optional[bool] = None
    flags: list[str] = field(default_factory=list)


@dataclass
class AllMeasurements:
    across_shoulder_mm: Optional[Measurement] = None
    shoulder_slope_deg: Optional[Measurement] = None
    front_length_mm: Optional[Measurement] = None
    bust_girth_mm: Optional[Measurement] = None
    underbust_girth_mm: Optional[Measurement] = None
    waist_girth_mm: Optional[Measurement] = None
    hip_girth_mm: Optional[Measurement] = None
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear(c1: tuple[int,int], c2: tuple[int,int], scale: float) -> float:
    """Euclidean distance in mm."""
    dx = c1[0] - c2[0]
    dy = c1[1] - c2[1]
    return np.hypot(dx, dy) * scale


def _y_diff(c1: tuple[int,int], c2: tuple[int,int], scale: float) -> float:
    """Vertical (y-only) distance in mm — for front_length."""
    return abs(c1[1] - c2[1]) * scale


def _angle_deg(c1: tuple[int,int], c2: tuple[int,int]) -> float:
    """Angle in degrees from c1 to c2."""
    dx = c2[0] - c1[0]
    dy = c2[1] - c1[1]
    return np.degrees(np.arctan2(dy, dx))


# ---------------------------------------------------------------------------
# Ramanujan ellipse girth approximation
# ---------------------------------------------------------------------------

def ellipse_perimeter_ramanujan(a: float, b: float) -> float:
    """
    Ramanujan approximation for ellipse perimeter:
    P ≈ π(a+b)(1 + 3h/(10+√(4-3h)))
    where h = ((a-b)/(a+b))²
    a = semi-major axis, b = semi-minor axis (both in same units)
    """
    if a <= 0 or b <= 0:
        return 0.0
    h = ((a - b) / (a + b)) ** 2
    factor = 1 + (3 * h) / (10 + np.sqrt(4 - 3 * h))
    return np.pi * (a + b) * factor


def _girth(front_L: tuple[int,int], front_R: tuple[int,int],
           side: tuple[int,int], scale: float) -> float:
    """
    Compute girth from front (L,R) and side markers.
    Uses front width for the ellipse major axis and side marker x-position
    for the minor axis (body depth from centreline).

    Args:
        front_L, front_R: front-view left/right marker positions
        side: side-view marker position (cx, cy) — its x is body depth from edge
        scale: mm per pixel

    Returns:
        Girth in mm (Ramanujan ellipse perimeter)
    """
    front_width = _linear(front_L, front_R, scale)
    front_semi = front_width / 2.0

    # Side depth: side marker's x from image edge approximates body depth.
    # The body centreline is roughly at x_mid of the front image.
    # side[0] is the x of the side marker (body surface in side view).
    # For the side view, body depth = side_x - image_left_edge.
    # Use side[0] itself as the depth proxy (it's the body surface).
    side_depth_px = float(side[0])
    side_depth_mm = side_depth_px * scale

    return ellipse_perimeter_ramanujan(front_semi, side_depth_mm)


# ---------------------------------------------------------------------------
# Main measurement function
# ---------------------------------------------------------------------------

def compute_measurements(labels: dict[str, tuple[int,int]],
                        side_labels: dict[str, tuple[int,int]],
                        scale: float,
                        human_reads: Optional[dict[str, float]] = None,
                        front_result=None) -> AllMeasurements:
    """
    Compute all measurements from labelled landmark positions.

    Args:
        labels: front-view landmark dict (name → (cx, cy))
        side_labels: side-view landmark dict
        scale: mm per pixel
        human_reads: optional {name: mm} e.g. {"bust": 92.0, "waist": 78.0}
                   Human reads from the printed band numbers.
    """
    m = AllMeasurements()
    hr = human_reads or {}
    scale_mm_per_px = scale  # alias clarity

    # --- Linear measurements ---
    # across_shoulder: sh_tip_L ↔ sh_tip_R
    if "sh_tip_L" in labels and "sh_tip_R" in labels:
        val = _linear(labels["sh_tip_L"], labels["sh_tip_R"], scale_mm_per_px)
        # Confidence: based on number of markers present
        conf = "high"
        app_read = val
        human_read = hr.get("across_shoulder")
        agree = None
        if human_read is not None:
            agree = abs(val - human_read) <= 20.0
            if not agree:
                conf = "low"
        m.across_shoulder_mm = Measurement(value=val, confidence=conf,
                                            human_read_mm=human_read,
                                            app_read_mm=app_read, agree=agree)
    else:
        m.flags.append("SKIP: across_shoulder (missing sh_tip_L or sh_tip_R)")

    # shoulder_slope: hps_R → sh_tip_R, angle
    if "hps_R" in labels and "sh_tip_R" in labels:
        deg = _angle_deg(labels["hps_R"], labels["sh_tip_R"])
        m.shoulder_slope_deg = Measurement(value=abs(deg), confidence="med",
                                              human_read_mm=None, app_read_mm=abs(deg),
                                              agree=None)
    else:
        m.flags.append("SKIP: shoulder_slope (missing hps_R or sh_tip_R)")

    # front_length: hps_R → cf_waist (y-only, not diagonal)
    if "hps_R" in labels and "cf_waist" in labels:
        val = _y_diff(labels["hps_R"], labels["cf_waist"], scale_mm_per_px)
        m.front_length_mm = Measurement(value=val, confidence="high",
                                         human_read_mm=None, app_read_mm=val, agree=None)
    else:
        m.flags.append("SKIP: front_length (missing hps_R or cf_waist)")

    # --- Girth measurements ---
    def girth(name: str, l_key: str, r_key: str, s_key: str,
              conf_override: Optional[str] = None) -> Optional[Measurement]:
        if l_key not in labels or r_key not in labels:
            m.warnings.append(f"SKIP: {name} (missing {l_key} or {r_key})")
            return None
        if s_key not in side_labels:
            m.warnings.append(f"SKIP: {name} (missing {s_key})")
            return None

        val = _girth(labels[l_key], labels[r_key], side_labels[s_key], scale_mm_per_px)
        human_read = hr.get(name)
        conf = conf_override or "med"  # girth confidence is always at best med
        agree = None
        if human_read is not None:
            delta = abs(val - human_read)
            agree = delta <= 20.0
            if delta > 20:
                conf = "low"
            elif delta <= 10:
                conf = "high"
        return Measurement(value=val, confidence=conf,
                            human_read_mm=human_read, app_read_mm=val, agree=agree)

    m.bust_girth_mm       = girth("bust",       "bust_L",       "bust_R",       "bust_side")
    m.underbust_girth_mm  = girth("underbust",  "underbust_L",  "underbust_R",  "underbust_side")
    m.waist_girth_mm      = girth("waist",      "waist_L",      "waist_R",      "waist_side")
    m.hip_girth_mm        = girth("hip",        "hip_L",        "hip_R",        "hip_side")

    # --- Level mismatch → degrade confidence ---
    # If LEVEL_MISMATCH flags were set during labelling, mark girth confidence as low
    for flag in m.flags:
        if "LEVEL_MISMATCH" in flag:
            for g in [m.bust_girth_mm, m.underbust_girth_mm, m.waist_girth_mm,
                      m.hip_girth_mm]:
                if g and g.confidence != "low":
                    g.confidence = "low"
                    g.flags.append(flag)

    return m


def measurements_to_dict(measurements: AllMeasurements) -> dict:
    """Serialize AllMeasurements to the JSON schema from SPEC.md §4.2."""
    def _m(name: str, m_: Optional[Measurement]) -> dict:
        if m_ is None:
            return {"value": 0.0, "confidence": "low",
                    "human_read_mm": None, "app_read_mm": 0.0, "agree": None}
        return {
            "value":         round(m_.value, 1),
            "confidence":    m_.confidence,
            "human_read_mm": (round(m_.human_read_mm, 1) if m_.human_read_mm is not None else None),
            "app_read_mm":  round(m_.app_read_mm, 1) if m_.app_read_mm is not None else 0.0,
            "agree":        m_.agree,
        }

    return {
        "across_shoulder_mm": _m("across_shoulder", measurements.across_shoulder_mm),
        "bust_girth_mm":      _m("bust",             measurements.bust_girth_mm),
        "underbust_girth_mm": _m("underbust",         measurements.underbust_girth_mm),
        "waist_girth_mm":     _m("waist",             measurements.waist_girth_mm),
        "hip_girth_mm":       _m("hip",               measurements.hip_girth_mm),
    }


def landmarks_to_dict(labels: dict[str, tuple[int,int]],
                     side_labels: dict[str, tuple[int,int]]) -> dict:
    """Serialize landmarks to JSON."""
    out = {}
    for name, (cx, cy) in labels.items():
        out[name] = [cx, cy]
    for name, (cx, cy) in side_labels.items():
        out[name] = [cx, cy]
    return out