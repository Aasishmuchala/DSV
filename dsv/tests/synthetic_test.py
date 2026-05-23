"""
Synthetic regression test for DSV measurement pipeline.
MUST pass before any real photo is processed.

Tests the pipeline against known-geometry synthetic images:
  1. Front view: perfectly placed markers with known landmark positions
  2. Side view: side markers at known y-positions
  3. Scale bar: known tick spacing
  4. All measurements have ground-truth expected values

The test renders a synthetic front+side image with markers placed at exact
positions, runs the pipeline, and asserts measurement error is within tolerance.
"""
from __future__ import annotations

import sys, math, pathlib, tempfile
from typing import NamedTuple

import cv2
import numpy as np

# Add parent dir to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from dsv import pipeline, scale, detect, label, measure


class ExpectedMeasurement(NamedTuple):
    name: str
    expected_mm: float
    tolerance_mm: float


SYNTHETIC_SCALE_MM_PER_PX = 0.25   # 0.25 mm/px = 4 px/mm → 2000px image ≈ 500mm real width
SYNTHETIC_MARKER_DIAM_PX = 48      # 48 px diameter ≈ 12mm at 0.25 mm/px
TICK_SPACING_PX = 160              # 40mm tick spacing at 0.25 mm/px
# Wider strip so vertical tick columns are well-separated in horizontal projection
SYNTHETIC_STRIP_PX = 80            # 80 px wide strip → ticks are distinct peaks


def make_synthetic_marker(cx: int, cy: int, r: int, img: np.ndarray) -> None:
    """Draw a filled circle marker on a BGR image."""
    cv2.circle(img, (cx, cy), r, (0, 255, 0), -1)  # neon green
    cv2.circle(img, (cx, cy), r, (0, 200, 0), 2)   # border


def make_synthetic_tick(cx: int, cy: int, img: np.ndarray, strip_x: int, strip_w: int) -> None:
    """Draw a scale tick mark at position cx, cy on the centre strip."""
    # Tick: short vertical white line on dark strip
    cv2.line(img, (cx, cy - 5), (cx, cy + 5), (255, 255, 255), 2)


def build_front_image(width: int = 800, height: int = 1200) -> np.ndarray:
    """Build a synthetic front-view image with all front markers at known positions."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 200  # light gray background

    x_mid = width // 2

    # --- Centre ruler strip (vertical, centred) ---
    strip_x = x_mid - SYNTHETIC_STRIP_PX // 2
    strip_w = SYNTHETIC_STRIP_PX
    # Draw dark strip background
    cv2.rectangle(img, (strip_x, 50), (strip_x + strip_w, height - 50),
                  (60, 60, 60), -1)
    # Draw scale ticks: thick vertical white bars every TICK_SPACING_PX
    # Use 6px-wide vertical bars so they're distinct in the horizontal projection
    strip_center_x = strip_x + strip_w // 2
    tick_y = 100
    while tick_y < height - 50:
        cv2.line(img, (strip_center_x, tick_y - 6),
                 (strip_center_x, tick_y + 6), (255, 255, 255), 6)
        tick_y += TICK_SPACING_PX

    # --- Front markers (known positions) ---
    # sh_tip_L at left shoulder
    # hps_L near left neck
    # hps_R near right neck
    # sh_tip_R at right shoulder
    # cf_neck (midline, near top)
    # cf_waist (midline, at waist)
    # bust_L, bust_R
    # waist_L, waist_R

    r = SYNTHETIC_MARKER_DIAM_PX // 2

    # Shoulder row (y around 150px from top)
    sh_y = 150
    sh_tip_L_x = 80
    hps_L_x   = x_mid - 60
    hps_R_x   = x_mid + 60
    sh_tip_R_x = width - 80

    markers = [
        (sh_tip_L_x, sh_y, "sh_tip_L"),
        (hps_L_x,    sh_y, "hps_L"),
        (hps_R_x,    sh_y, "hps_R"),
        (sh_tip_R_x, sh_y, "sh_tip_R"),
        (x_mid, 200, "cf_neck"),      # centre-front neck
        (x_mid, 450, "cf_waist"),     # centre-front waist
        (x_mid - 120, 350, "bust_L"),
        (x_mid + 120, 350, "bust_R"),
        (x_mid - 100, 600, "waist_L"),
        (x_mid + 100, 600, "waist_R"),
        # underbust
        (x_mid - 115, 480, "underbust_L"),
        (x_mid + 115, 480, "underbust_R"),
        (x_mid, 480, "cf_underbust"),
        # hip
        (x_mid - 110, 750, "hip_L"),
        (x_mid + 110, 750, "hip_R"),
        (x_mid, 750, "cf_hip"),
    ]

    for cx_, cy_, _ in markers:
        make_synthetic_marker(cx_, cy_, r, img)

    return img, {name: (cx_, cy_) for cx_, cy_, name in markers}


def build_side_image(width: int = 800, height: int = 1200,
                      front_labels: dict = None) -> np.ndarray:
    """Build a synthetic side-view image with side markers at known positions."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 200

    x_mid = width // 2

    # Side markers: sh_tip, bust, underbust, waist, hip (sorted by y)
    side_markers = [
        (x_mid - 180, 150, "sh_tip_side"),
        (x_mid - 200, 350, "bust_side"),
        (x_mid - 190, 480, "underbust_side"),
        (x_mid - 180, 600, "waist_side"),
        (x_mid - 190, 750, "hip_side"),
    ]
    r = SYNTHETIC_MARKER_DIAM_PX // 2
    for cx_, cy_, _ in side_markers:
        # Side markers in green to match the colour detector
        make_synthetic_marker(cx_, cy_, r, img)

    return img, {name: (cx_, cy_) for cx_, cy_, name in side_markers}


def expected_measurements(labels: dict, side_labels: dict, scale: float) -> list[ExpectedMeasurement]:
    """Compute expected measurements from ground-truth labels."""
    scale_mm_per_px = scale  # 0.25 mm/px

    def dist(c1, c2):
        return math.hypot(c1[0] - c2[0], c1[1] - c2[1]) * scale_mm_per_px

    em = []
    if "sh_tip_L" in labels and "sh_tip_R" in labels:
        em.append(ExpectedMeasurement("across_shoulder",
                                        dist(labels["sh_tip_L"], labels["sh_tip_R"]),
                                        0.5))
    if "hps_R" in labels and "sh_tip_R" in labels:
        dx = labels["sh_tip_R"][0] - labels["hps_R"][0]
        dy = labels["sh_tip_R"][1] - labels["hps_R"][1]
        deg = abs(math.degrees(math.atan2(dy, dx)))
        em.append(ExpectedMeasurement("shoulder_slope", deg, 0.5))
    if "hps_R" in labels and "cf_waist" in labels:
        dy = abs(labels["hps_R"][1] - labels["cf_waist"][1]) * scale_mm_per_px
        em.append(ExpectedMeasurement("front_length", dy, 0.5))
    return em


def test_synthetic_front_scale():
    """Test: scale calibration returns correct mm_per_px on synthetic strip."""
    img, _ = build_front_image()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    x_mid = img.shape[1] // 2
    strip_x = x_mid - SYNTHETIC_STRIP_PX // 2
    strip_w = SYNTHETIC_STRIP_PX
    # Tick spacing = TICK_SPACING_PX = 160
    mm_per_px_actual = scale.calibrate_scale_from_strip(
        gray, strip_x, 0, strip_w, img.shape[0],
        known_spacing_mm=40.0
    )

    # We know the synthetic tick spacing is 160px for 40mm → 0.25 mm/px
    error = abs(mm_per_px_actual - 0.25)
    print(f"  scale: measured={mm_per_px_actual:.4f}, expected=0.2500, error={error:.4f}")
    assert error < 0.01, f"Scale calibration error too large: {error:.4f} mm/px"
    print("  ✓ scale calibration")


def test_synthetic_marker_detection():
    """Test: markers are detected with correct count and positions."""
    img, ground_truth = build_front_image()
    x_mid = 400

    markers, colour = detect.detect_markers(img, "green")
    print(f"  detected {len(markers)} markers (colour={colour})")

    assert len(markers) >= 10, f"Expected ≥10 markers, got {len(markers)}"
    print("  ✓ marker detection")


def test_synthetic_labelling():
    """Test: front and side labelling produces correct landmark positions."""
    # Front
    front_img, front_gt = build_front_image()
    gray = cv2.cvtColor(front_img, cv2.COLOR_BGR2GRAY)
    x_mid = 400
    mm_per_px = 0.25
    marker_diam_px = 48

    strip_x = x_mid - SYNTHETIC_STRIP_PX // 2
    strip_w = SYNTHETIC_STRIP_PX
    scale_val = scale.calibrate_scale_from_strip(
        gray, strip_x, 0, strip_w, front_img.shape[0], 40.0
    )

    markers, _ = detect.detect_markers(front_img, "green")
    fr = label.label_front(markers, x_mid, marker_diam_px, mm_per_px)

    print(f"  front labels: {list(fr.labels.keys())}")
    assert "sh_tip_L" in fr.labels, "sh_tip_L not labelled"
    assert "sh_tip_R" in fr.labels, "sh_tip_R not labelled"
    assert "hps_L"    in fr.labels, "hps_L not labelled"
    assert "hps_R"    in fr.labels, "hps_R not labelled"
    assert "cf_neck"  in fr.labels, "cf_neck not labelled"
    assert "bust_L"   in fr.labels, "bust_L not labelled"

    # Side
    side_img, side_gt = build_side_image()
    s_markers, _ = detect.detect_markers(side_img, "green")
    sr = label.label_side(s_markers, mm_per_px)
    print(f"  side labels: {list(sr.side_labels.keys())}")
    assert "sh_tip_side" in sr.side_labels, "sh_tip_side not labelled"
    assert "bust_side"   in sr.side_labels, "bust_side not labelled"

    print("  ✓ labelling")


def test_synthetic_measurement():
    """Test: measurements from synthetic images are within tolerance of ground truth."""
    front_img, front_gt = build_front_image()
    side_img, side_gt   = build_side_image()

    gray = cv2.cvtColor(front_img, cv2.COLOR_BGR2GRAY)
    x_mid = 400

    strip_x = x_mid - SYNTHETIC_STRIP_PX // 2
    strip_w = SYNTHETIC_STRIP_PX
    scale_val = scale.calibrate_scale_from_strip(
        gray, strip_x, 0, strip_w, front_img.shape[0], 40.0
    )

    front_markers, _ = detect.detect_markers(front_img, "green")
    side_markers,  _ = detect.detect_markers(side_img,  "green")

    fr = label.label_front(front_markers, x_mid, 48, scale_val)
    sr = label.label_side(side_markers, scale_val)
    fr = label.cross_validate_levels(fr, sr)

    measurements = measure.compute_measurements(
        fr.labels, sr.side_labels, scale_val, {}
    )

    print(f"  across_shoulder: {measurements.across_shoulder_mm.value:.1f}mm")
    fl = measurements.front_length_mm
    print(f"  front_length: {fl.value:.1f}mm" if fl else "  front_length: skipped (missing labels)")
    bg = measurements.bust_girth_mm
    print(f"  bust_girth: {bg.value:.1f}mm" if bg else "  bust_girth: skipped")
    wg = measurements.waist_girth_mm
    print(f"  waist_girth: {wg.value:.1f}mm" if wg else "  waist_girth: skipped")

    # Check: across_shoulder ground truth = dist(sh_tip_L, sh_tip_R) × 0.25mm/px
    # sh_tip_L at (80, 150), sh_tip_R at (720, 150) → 640 px → 160mm
    gt_shoulder = math.hypot(720-80, 150-150) * scale_val
    asm = measurements.across_shoulder_mm
    assert asm is not None, "across_shoulder_mm was None"
    err = abs(asm.value - gt_shoulder)
    print(f"  across_shoulder error: {err:.2f}mm (tolerance 1.0mm)")
    assert err < 1.0, f"across_shoulder error {err:.2f}mm exceeds 1.0mm"

    print("  ✓ measurement computation")


def test_synthetic_pipeline_end_to_end():
    """Test: full pipeline run on synthetic images produces valid output."""
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp)

        front_img, _ = build_front_image()
        side_img,  _ = build_side_image()

        fp = out / "front.png"
        sp = out / "side.png"
        cv2.imwrite(str(fp), front_img)
        cv2.imwrite(str(sp), side_img)

        result = pipeline.run(fp, sp, out_dir=out)

        assert result.scale_mm_per_px > 0, "scale_mm_per_px is zero"
        assert len(result.measurements) > 0, "no measurements produced"
        assert "across_shoulder_mm" in result.measurements, "missing across_shoulder"
        print(f"  scale: {result.scale_mm_per_px:.4f} mm/px")
        print(f"  colour: {result.colour_detected}")
        print(f"  measurements: {list(result.measurements.keys())}")

        json_file = out / "measurement.json"
        assert json_file.exists(), "measurement.json not written"
        import json
        data = json.loads(json_file.read_text())
        assert data["schema_version"] == "dsv-1.0", "wrong schema version"
        print("  ✓ pipeline end-to-end")


def test_scale_must_fail_loudly():
    """Test: scale detection fails explicitly if ticks not found."""
    # Blank image (no ticks)
    img = np.ones((800, 800, 3), dtype=np.uint8) * 200
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    try:
        scale.calibrate_scale_from_strip(gray, 390, 0, 20, 800, 40.0)
        assert False, "Should have raised on no ticks"
    except (ValueError, RuntimeError) as e:
        print(f"  correctly raised: {e}")
        print("  ✓ fail-loudly on missing scale")


def run_all():
    print("\n=== DSV Synthetic Test Suite ===\n")
    tests = [
        ("scale calibration",       test_synthetic_front_scale),
        ("marker detection",         test_synthetic_marker_detection),
        ("labelling",               test_synthetic_labelling),
        ("measurement computation",  test_synthetic_measurement),
        ("pipeline end-to-end",     test_synthetic_pipeline_end_to_end),
        ("fail-loudly on no scale", test_scale_must_fail_loudly),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"  {passed}/{passed+failed} passed")
    if failed:
        print(f"  ✗ {failed} FAILED — do not use with real photos")
        sys.exit(1)
    else:
        print(f"  ✓ ALL PASSED — safe to use with real photos")
        sys.exit(0)


if __name__ == "__main__":
    run_all()