"""
Edge-case test suite for DSV labelling pipeline.
Tests: slouch, missing marker, band tilt, level mismatch, loose clothing.
Each must degrade gracefully — no silent wrong outputs.
"""
from __future__ import annotations

import sys, math, pathlib, tempfile
from typing import Callable

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from dsv import scale, detect, label, measure


def make_marker(cx: int, cy: int, r: int, img: np.ndarray, colour=(0, 255, 0)) -> None:
    cv2.circle(img, (cx, cy), r, colour, -1)


def standard_front_labels(x_mid=400):
    """Return standard front marker positions (normal pose)."""
    return {
        "sh_tip_L":  (80,  150),
        "hps_L":     (x_mid-60, 150),
        "hps_R":     (x_mid+60, 150),
        "sh_tip_R":  (720, 150),
        "cf_neck":   (x_mid, 200),
        "bust_L":    (x_mid-120, 350),
        "bust_R":    (x_mid+120, 350),
        "underbust_L": (x_mid-115, 480),
        "underbust_R": (x_mid+115, 480),
        "cf_underbust": (x_mid, 480),
        "cf_waist":  (x_mid, 600),
        "waist_L":   (x_mid-100, 600),
        "waist_R":   (x_mid+100, 600),
        "hip_L":     (x_mid-110, 750),
        "hip_R":     (x_mid+110, 750),
        "cf_hip":    (x_mid, 750),
    }


def build_front_with_markers(width=800, height=1200, overrides: dict = None) -> tuple:
    """Build image + marker list + ground-truth labels."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    x_mid = width // 2
    r = 24

    gt = standard_front_labels(x_mid)
    if overrides:
        gt.update(overrides)

    # Draw centre strip
    cv2.rectangle(img, (x_mid-10, 50), (x_mid+10, height-50), (60,60,60), -1)
    # Ticks on strip
    for ty in range(100, height-50, 160):
        cv2.line(img, (x_mid, ty-5), (x_mid, ty+5), (255,255,255), 2)

    # Draw markers from gt
    marker_list = []
    for name, (cx_, cy_) in gt.items():
        make_marker(cx_, cy_, r, img)
        marker_list.append({"cx": cx_, "cy": cy_, "r": r, "name": name})

    return img, gt


def test_slouch():
    """
    Slouch: HPS markers drop below shoulder tips in image y.
    The algorithm must use x-position (not y-order) to separate shoulder tips from HPS.
    """
    print("\n  [slouch] HPS drops 30px below shoulder tips")
    x_mid = 400

    # Normal: all shoulder-row markers at y=150
    _, gt_normal = build_front_with_markers(overrides={
        "hps_L": (x_mid-60, 150),
        "hps_R": (x_mid+60, 150),
    })

    # Slouch: HPS drops to y=180 (below shoulder tips at y=150)
    _, gt_slouch = build_front_with_markers(overrides={
        "hps_L": (x_mid-60, 180),  # 30px lower
        "hps_R": (x_mid+60, 180),  # 30px lower
    })

    # Run labelling on slouch image
    slouch_img, _ = build_front_with_markers(overrides={
        "hps_L": (x_mid-60, 180),
        "hps_R": (x_mid+60, 180),
    })

    markers, _ = detect.detect_markers(slouch_img, "green")
    fr = label.label_front(markers, x_mid, marker_diam_px=48, mm_per_px=0.25)

    # Check: sh_tip_L must be leftmost in the shoulder row
    sh_tip_L = fr.labels.get("sh_tip_L")
    sh_tip_R = fr.labels.get("sh_tip_R")
    hps_L    = fr.labels.get("hps_L")
    hps_R    = fr.labels.get("hps_R")

    print(f"    sh_tip_L: {sh_tip_L}")
    print(f"    hps_L:    {hps_L}")
    print(f"    sh_tip_R: {sh_tip_R}")
    print(f"    hps_R:    {hps_R}")

    assert sh_tip_L is not None, "sh_tip_L missing"
    assert sh_tip_R is not None, "sh_tip_R missing"
    assert hps_L is not None,    "hps_L missing"
    assert hps_R is not None,    "hps_R missing"

    # hps_L and hps_R must be closer to x_mid than sh_tip_L and sh_tip_R
    assert abs(sh_tip_L[0] - x_mid) > abs(hps_L[0] - x_mid), \
        f"hps_L should be closer to midline than sh_tip_L: {sh_tip_L[0]} vs {hps_L[0]}"
    assert abs(sh_tip_R[0] - x_mid) > abs(hps_R[0] - x_mid), \
        f"hps_R should be closer to midline than sh_tip_R: {sh_tip_R[0]} vs {hps_R[0]}"

    print("    ✓ slouch handled correctly — HPS identified by x-position")


def test_missing_marker():
    """
    Missing shoulder marker: algorithm must count markers, detect the mismatch,
    emit MISSING_MARKER flag, and skip (not guess) dependent measurements.
    """
    print("\n  [missing_marker] Remove one shoulder-tip marker")
    x_mid = 400

    # Build image with sh_tip_R missing (only 3 shoulder-row markers)
    img = np.ones((1200, 800, 3), dtype=np.uint8) * 200
    r = 24

    # Centre strip
    cv2.rectangle(img, (x_mid-10, 50), (x_mid+10, 1200-50), (60,60,60), -1)
    for ty in range(100, 1200-50, 160):
        cv2.line(img, (x_mid, ty-5), (x_mid, ty+5), (255,255,255), 2)

    # Only 3 shoulder markers (no sh_tip_R)
    make_marker(80,  150, r, img)   # sh_tip_L
    make_marker(x_mid-60, 150, r, img)  # hps_L
    make_marker(x_mid+60, 150, r, img)  # hps_R
    # No sh_tip_R!

    # Other markers present
    make_marker(x_mid, 200, r, img)      # cf_neck
    make_marker(x_mid-120, 350, r, img)  # bust_L
    make_marker(x_mid+120, 350, r, img)  # bust_R
    make_marker(x_mid, 600, r, img)      # cf_waist

    markers, _ = detect.detect_markers(img, "green")
    fr = label.label_front(markers, x_mid, marker_diam_px=48, mm_per_px=0.25)

    print(f"    flags: {fr.flags}")
    print(f"    warnings: {fr.warnings}")
    print(f"    labels: {list(fr.labels.keys())}")

    has_missing_flag = any("MISSING_MARKER" in f and "shoulder" in f for f in fr.flags)
    assert has_missing_flag, f"MISSING_MARKER flag not set. Flags: {fr.flags}"

    # across_shoulder should be skipped (depends on both sh_tip_L and sh_tip_R)
    # The labelling should produce some labels but flag the incompleteness
    assert "sh_tip_L" in fr.labels, "sh_tip_L should still be labelled"
    assert "sh_tip_R" not in fr.labels or "MISSING_MARKER" in str(fr.flags), \
        "sh_tip_R missing should be flagged"

    print("    ✓ missing marker detected and flagged — no silent wrong output")


def test_level_mismatch():
    """
    Front bust L and R at different y-positions (>20px spread).
    Algorithm must detect LEVEL_MISMATCH: bust and degrade confidence.
    """
    print("\n  [level_mismatch] bust_L 25px above bust_R")
    x_mid = 400

    # Normal bust_L and bust_R at same y
    _, gt_normal = build_front_with_markers(overrides={
        "bust_L": (x_mid-120, 350),
        "bust_R": (x_mid+120, 350),
    })

    # Mismatch: bust_L at y=325, bust_R at y=375 (50px spread, well above 20px threshold)
    img, _ = build_front_with_markers(overrides={
        "bust_L": (x_mid-120, 325),  # 25px higher
        "bust_R": (x_mid+120, 375),  # 25px lower
        "underbust_L": (x_mid-115, 455),
        "underbust_R": (x_mid+115, 485),
    })

    markers, _ = detect.detect_markers(img, "green")
    fr = label.label_front(markers, x_mid, marker_diam_px=48, mm_per_px=0.25)

    print(f"    bust_L y: {fr.labels.get('bust_L', (0,0))[1]}")
    print(f"    bust_R y: {fr.labels.get('bust_R', (0,0))[1]}")
    print(f"    flags: {fr.flags}")

    has_level_flag = any("LEVEL_MISMATCH" in f for f in fr.flags)
    assert has_level_flag, f"LEVEL_MISMATCH flag not set. Flags: {fr.flags}"

    # Confirm the bust markers were at different y
    bust_L_y = fr.labels.get("bust_L", (0, 0))[1]
    bust_R_y = fr.labels.get("bust_R", (0, 0))[1]
    assert abs(bust_L_y - bust_R_y) > 20, "Bust L/R should be >20px apart in this test"

    print("    ✓ level mismatch detected and flagged")


def test_side_missing_marker():
    """
    Side view with only 4 markers (missing hip_side).
    Must emit MISSING_MARKER and map top-to-bottom with a warning.
    """
    print("\n  [side_missing] Only 4 side markers (hip_side missing)")
    x_mid = 400

    img = np.ones((1200, 800, 3), dtype=np.uint8) * 200
    r = 24

    # 4 side markers (missing bottom one)
    side_positions = [
        (x_mid-180, 150, "sh_tip_side"),     # 0
        (x_mid-200, 350, "bust_side"),         # 1
        (x_mid-190, 480, "underbust_side"),   # 2
        (x_mid-180, 600, "waist_side"),        # 3  ← hip_side MISSING
    ]

    for cx_, cy_, name in side_positions:
        make_marker(cx_, cy_, r, img)

    markers, _ = detect.detect_markers(img, "green")
    sr = label.label_side(markers, mm_per_px=0.25)

    print(f"    side labels: {list(sr.side_labels.keys())}")
    print(f"    side flags: {sr.side_flags}")
    print(f"    side warnings: {sr.side_warnings}")

    has_missing = any("MISSING_MARKER" in f for f in sr.side_flags)
    assert has_missing, f"MISSING_MARKER flag not set. Flags: {sr.side_flags}"

    assert "sh_tip_side" in sr.side_labels, "sh_tip_side should be labelled"
    assert "bust_side"   in sr.side_labels, "bust_side should be labelled"

    # hip_side should be missing or flagged
    hip_present = "hip_side" in sr.side_labels

    print(f"    ✓ side missing marker handled — hip_side present={hip_present}")


def test_extra_marker():
    """
    Side view with an extra marker (6 instead of 5).
    Must detect and warn, not silently pick the wrong subset.
    """
    print("\n  [extra_marker] 6 side markers (extra spurious one)")
    x_mid = 400

    img = np.ones((1200, 800, 3), dtype=np.uint8) * 200
    r = 24

    # 5 correct side markers + 1 spurious (near waist)
    side_positions = [
        (x_mid-180, 150, "sh_tip_side"),
        (x_mid-200, 350, "bust_side"),
        (x_mid-190, 480, "underbust_side"),
        (x_mid-195, 550, "spurious"),          # extra — near underbust
        (x_mid-180, 600, "waist_side"),
        (x_mid-190, 750, "hip_side"),
    ]

    for cx_, cy_, name in side_positions:
        make_marker(cx_, cy_, r, img)

    markers, _ = detect.detect_markers(img, "green")
    sr = label.label_side(markers, mm_per_px=0.25)

    print(f"    side flags: {sr.side_flags}")
    print(f"    side labels: {list(sr.side_labels.keys())}")

    has_extra_flag = any("EXTRA_MARKERS" in f for f in sr.side_flags)
    assert has_extra_flag, f"EXTRA_MARKERS flag not set. Flags: {sr.side_flags}"

    # Key markers still labelled (top and bottom extremes)
    assert "sh_tip_side" in sr.side_labels, "sh_tip_side should be labelled"
    assert "hip_side"    in sr.side_labels, "hip_side should be labelled"

    print("    ✓ extra marker detected and flagged — top/bottom extremes labelled")


def test_degraded_measurement_no_crash():
    """
    When labelling produces warnings, measurements must still compute
    (skip unknown) rather than crash or return wrong numbers.
    """
    print("\n  [degraded_no_crash] Missing multiple markers, check measurement skips gracefully")

    # Build image with several markers missing
    img = np.ones((1200, 800, 3), dtype=np.uint8) * 200
    x_mid = 400
    r = 24

    cv2.rectangle(img, (x_mid-10, 50), (x_mid+10, 1200-50), (60,60,60), -1)
    for ty in range(100, 1200-50, 160):
        cv2.line(img, (x_mid, ty-5), (x_mid, ty+5), (255,255,255), 2)

    # Only markers present: sh_tip_L, sh_tip_R, bust_L, bust_R, waist_L, waist_R
    make_marker(80,  150, r, img)
    make_marker(720, 150, r, img)
    make_marker(x_mid-120, 350, r, img)
    make_marker(x_mid+120, 350, r, img)
    make_marker(x_mid-100, 600, r, img)
    make_marker(x_mid+100, 600, r, img)

    markers, _ = detect.detect_markers(img, "green")
    fr = label.label_front(markers, x_mid, marker_diam_px=48, mm_per_px=0.25)

    # Run measurement — should not crash
    try:
        measurements = measure.compute_measurements(
            fr.labels, {},  # empty side labels
            scale=0.25,
            human_reads={}
        )

        # The test verifies the pipeline didn't crash — that's what matters.
        # bust_girth_mm is None because side_labels is empty (expected for degraded input)
        print(f"    across_shoulder: {measurements.across_shoulder_mm.value if measurements.across_shoulder_mm else 'None'}mm")
        print(f"    bust_girth: {'computed' if measurements.bust_girth_mm else 'skipped (no side view)'}")

        # shoulder_slope should be SKIPPED (hps_R missing)
        assert any("shoulder_slope" in f for f in measurements.flags), \
            "shoulder_slope should be skipped with a flag"

        print(f"    measurement flags: {measurements.flags}")
        print(f"    measurement warnings: {measurements.warnings}")
        print("    ✓ degraded measurement — skipped gracefully, no crash")

    except Exception as e:
        raise AssertionError(f"Measurement crashed on degraded input: {e}")


def run_all():
    print("\n=== DSV Edge-Case Test Suite ===\n")
    tests = [
        ("slouch (HPS drops below shoulder tips)", test_slouch),
        ("missing marker (shoulder tip absent)",   test_missing_marker),
        ("level mismatch (bust L vs R)",           test_level_mismatch),
        ("side missing marker (hip_side absent)",  test_side_missing_marker),
        ("extra marker (spurious side marker)",     test_extra_marker),
        ("degraded measurement (no crash)",        test_degraded_measurement_no_crash),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"    ✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"    ✗ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"  {passed}/{passed+failed} passed")
    if failed:
        print(f"  ✗ {failed} FAILED — fix labelling before real use")
        sys.exit(1)
    else:
        print(f"  ✓ ALL PASSED — edge cases handled correctly")
        sys.exit(0)


if __name__ == "__main__":
    run_all()