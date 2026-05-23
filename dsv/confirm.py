"""Human-vs-app read confirm screen + quality gates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QualityResult:
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    agree_results: dict[str, dict] = field(default_factory=dict)  # name → {human, app, agree, delta}


AGREE_THRESHOLD_MM = 20.0  # tighten to 15mm after pilot data


def band_tilt_check(labels: dict[str, tuple[int, int]],
                    strip_x: int, strip_y: int, strip_w: int, strip_h: int,
                    band_y: int, threshold_deg: float = 3.0) -> Optional[str]:
    """
    Check if a band's tick line is tilted beyond threshold.
    Uses the row of tick marks along the centre strip at the band's y level.
    Returns flag string or None.
    """
    # For now, approximate: check if the band has asymmetric y on L vs R
    # In production, you'd align the strip tick line with the band
    pass  # stubs — real implementation uses scale tick detection


def loose_clothing_detect(front_labels: dict[str, tuple[int, int]],
                          body_outline_px: Optional[list[tuple[int,int]]] = None) -> Optional[str]:
    """
    Detect loose clothing from band positions vs body outline.

    Algorithm:
    1. At each band level, compute angle of body outline tangent
    2. If band deviates from body outline by > ~15°, flag loose_clothing_suspected
    3. Alternatively: if distance from band markers to body outline > marker_diameter

    In v0, this is a heuristic stub. The real implementation would require
    silhouette extraction from the light-wall background.
    """
    # Stub: flag if bust_L and bust_R are suspiciously high above shoulder row
    if "bust_L" in front_labels and "hps_R" in front_labels:
        bust_y = front_labels["bust_L"][1]
        hps_y  = front_labels["hps_R"][1]
        # If bust is less than 30% of image height below shoulder, something is off
        if bust_y < 100 and hps_y < 100:
            return "loose_clothing_suspected"
    return None


def check_band_levels(front_labels: dict[str, tuple[int,int]],
                      side_labels: dict[str, tuple[int,int]],
                      tolerance_px: int = 20) -> list[str]:
    """Check L/R same-level within front view and front/side cross-level."""
    flags = []
    for level in ["bust", "underbust", "waist", "hip"]:
        l_key = f"{level}_L"
        r_key = f"{level}_R"
        s_key = f"{level}_side"
        if l_key in front_labels and r_key in front_labels:
            dy = abs(front_labels[l_key][1] - front_labels[r_key][1])
            if dy > tolerance_px:
                flags.append(f"LEVEL_MISMATCH: {level} (|y_L-y_R|={dy}px)")
        if l_key in front_labels and s_key in side_labels:
            dy = abs(front_labels[l_key][1] - side_labels[s_key][1])
            if dy > tolerance_px:
                flags.append(f"LEVEL_MISMATCH: {level}_front_vs_side (Δy={dy}px)")
    return flags


def check_agree(human_reads: dict[str, float],
                app_reads: dict[str, float],
                threshold_mm: float = AGREE_THRESHOLD_MM) -> dict[str, dict]:
    """
    Check human vs app agree per measurement.
    Returns dict: name → {human, app, agree, delta_mm}
    """
    results = {}
    for name in human_reads:
        if name not in app_reads:
            continue
        h = human_reads[name]
        a = app_reads[name]
        delta = abs(h - a)
        results[name] = {
            "human": h,
            "app":   a,
            "delta_mm": round(delta, 1),
            "agree": delta <= threshold_mm,
        }
    return results


def quality_gate(front_labels: dict[str, tuple[int,int]],
                 side_labels: dict[str, tuple[int,int]],
                 human_reads: Optional[dict[str,float]] = None,
                 marker_diam_px: int = 40) -> QualityResult:
    """
    Run all quality gates.
    Returns QualityResult with flags, warnings, and agree_results.
    """
    result = QualityResult()

    # 1. Missing markers — already flagged in labelling
    # 2. Level mismatches
    level_flags = check_band_levels(front_labels, side_labels)
    result.flags.extend(level_flags)

    # 3. Loose clothing detection
    loose = loose_clothing_detect(front_labels)
    if loose:
        result.flags.append(loose)

    # 4. Band tilt — stub (requires tick line detection)
    # 5. Read-confirm agree check
    if human_reads:
        app_reads = {}  # would come from measure.py
        agree_results = check_agree(human_reads, app_reads, AGREE_THRESHOLD_MM)
        result.agree_results = agree_results
        for name, r in agree_results.items():
            if not r["agree"]:
                result.warnings.append(
                    f"{name}: human={r['human']:.0f}cm, app={r['app']:.0f}cm, Δ={r['delta_mm']}mm > {AGREE_THRESHOLD_MM}mm"
                )

    return result


def format_confirm_screen(agree_results: dict[str, dict]) -> str:
    """
    Format agree/disagree results for display in the app confirm screen.
    Returns a text summary.
    """
    lines = []
    for name, r in agree_results.items():
        status = "✓" if r["agree"] else "✗ RETAKE"
        delta_str = f"+{r['delta_mm']}mm" if r['delta_mm'] else ""
        lines.append(f"  {status} {name:15s} human={r['human']:6.1f}cm  app={r['app']:6.1f}cm  {delta_str}")
    return "\n".join(lines)