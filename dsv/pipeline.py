"""DSV measurement pipeline — orchestrates all stages and emits JSON + annotated overlays."""
from __future__ import annotations

import json, pathlib, time
from dataclasses import dataclass, field, asdict

import cv2
import numpy as np

from . import ingest, scale, detect, label, measure, confirm


@dataclass
class PipelineConfig:
    """Configuration for the DSV pipeline."""
    # Colour strategy (auto-detect or specific)
    colour: str = "auto"  # "auto", "green", "cyan", "red", "fallback"
    # Marker diameter mm (for thresholds)
    marker_diam_mm: float = 16.0
    # Scale calibration: tick spacing on centre strip (mm)
    strip_tick_spacing_mm: float = 40.0
    # Scale calibration: tick spacing on band strips (mm)
    band_tick_spacing_mm: float = 25.0
    # Agree threshold for human vs app (mm)
    agree_threshold_mm: float = 20.0
    # Max image dimension for processing
    max_long_edge: int = 2000


@dataclass
class PipelineResult:
    """Full output of the DSV pipeline."""
    schema_version: str = "dsv-1.0"
    scale_mm_per_px: float = 0.0
    colour_detected: str = "unknown"
    measurements: dict = field(default_factory=dict)
    landmarks_px: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    agree_results: dict = field(default_factory=dict)
    processing_time_ms: float = 0.0
    front_overlay_path: str = ""
    side_overlay_path: str = ""
    # Internal data (not serialized to JSON)
    front_labels: dict = field(default_factory=dict)
    side_labels: dict = field(default_factory=dict)
    front_img: object = None
    side_img: object = None

    def to_dict(self) -> dict:
        """Serialize for JSON output (strips internal fields)."""
        d = asdict(self)
        # Remove internal-only fields
        del d["front_labels"]
        del d["side_labels"]
        del d["front_img"]
        del d["side_img"]
        return d

    def write_json(self, path: pathlib.Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                        encoding="utf-8")

    def write_overlay(self, path: pathlib.Path, img: np.ndarray,
                      front_labels: dict, side_labels: dict,
                      measurements: dict) -> None:
        """
        Draw annotated overlay on the image.
        - Landmark circles with name labels
        - Measurement lines between landmarks
        - Colour: green circles, blue lines, red warnings
        """
        overlay = img.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        def draw_marker(x, y, r, name: str, colour=(0, 255, 0)):
            cv2.circle(overlay, (x, y), int(r * 2), colour, 2)
            cv2.putText(overlay, name, (x + 6, y - 6), font, 0.5, colour, 1)

        # Draw front labels
        for name, (cx, cy) in front_labels.items():
            draw_marker(cx, cy, 12, name, (0, 255, 0))  # green
        # Draw side labels
        for name, (cx, cy) in side_labels.items():
            draw_marker(cx, cy, 12, name, (255, 0, 0))  # blue
        # Draw measurement lines
        line_colour = (0, 200, 255)  # yellow
        if "sh_tip_L" in front_labels and "sh_tip_R" in front_labels:
            p1, p2 = front_labels["sh_tip_L"], front_labels["sh_tip_R"]
            cv2.line(overlay, p1, p2, line_colour, 2)
        # Draw girth ellipses (front width arc)
        for level in ["bust", "underbust", "waist", "hip"]:
            lk = f"{level}_L"
            rk = f"{level}_R"
            sk = f"{level}_side"
            if lk in front_labels and rk in front_labels:
                cv2.line(overlay, front_labels[lk], front_labels[rk],
                         line_colour, 2)
                cv2.putText(overlay, f"{level}", front_labels[rk],
                            font, 0.5, line_colour, 1)

        cv2.imwrite(str(path), overlay)

    def save_overlays(self, out_dir: pathlib.Path) -> None:
        """Save front and side overlay images."""
        out_dir = pathlib.Path(out_dir)
        if self.front_img is not None and self.front_labels:
            fp = out_dir / "overlay_front.png"
            self.write_overlay(fp, self.front_img, self.front_labels,
                               {}, self.measurements)
            self.front_overlay_path = str(fp)
        if self.side_img is not None and self.side_labels:
            sp = out_dir / "overlay_side.png"
            self.write_overlay(sp, self.side_img, {},
                               self.side_labels, self.measurements)
            self.side_overlay_path = str(sp)


def run(front_path: pathlib.Path | str,
        side_path: pathlib.Path | str,
        human_reads: dict[str, float] | None = None,
        out_dir: pathlib.Path | str | None = None,
        config: PipelineConfig | None = None) -> PipelineResult:
    """
    Run the full DSV measurement pipeline.

    Args:
        front_path: path to front photo
        side_path:  path to side photo
        human_reads: optional {name: mm} from printed band numbers
        out_dir:    directory to write JSON + overlays (created if needed)
        config:     PipelineConfig, uses defaults if None

    Returns:
        PipelineResult with measurements, labels, flags, overlays

    Raises:
        RuntimeError on hard failures (tick detection, etc.)
    """
    t0 = time.time()
    cfg = config or PipelineConfig()
    out_dir = pathlib.Path(out_dir) if out_dir else pathlib.Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult()
    human_reads = human_reads or {}

    # -------------------------------------------------------------------------
    # Stage 1 — Ingest
    # -------------------------------------------------------------------------
    front_img, scale_front = ingest.load_image(pathlib.Path(front_path), cfg.max_long_edge)
    side_img,  scale_side  = ingest.load_image(pathlib.Path(side_path),  cfg.max_long_edge)
    result.front_img = front_img
    result.side_img  = side_img

    h, w = front_img.shape[:2]
    x_mid = w // 2

    # -------------------------------------------------------------------------
    # Stage 2 — Scale calibration
    # -------------------------------------------------------------------------
    # Auto-detect strip region
    strip_rect = scale.detect_scale_region(cv2.cvtColor(front_img, cv2.COLOR_BGR2GRAY))
    if strip_rect is None:
        raise RuntimeError("SCALE_DETECTION_FAILED: Could not find centre ruler strip. "
                           "Verify the DSV is correctly applied and the strip is visible.")
    strip_x, strip_y, strip_w, strip_h = strip_rect

    # Derive mm_per_px
    mm_per_px = scale.calibrate_scale_from_strip(
        cv2.cvtColor(front_img, cv2.COLOR_BGR2GRAY),
        strip_x, strip_y, strip_w, strip_h,
        cfg.strip_tick_spacing_mm
    )
    result.scale_mm_per_px = mm_per_px
    marker_diam_px = int(cfg.marker_diam_mm / mm_per_px)

    # -------------------------------------------------------------------------
    # Stage 3 — Marker detection
    # -------------------------------------------------------------------------
    if cfg.colour == "auto":
        markers_front, colour_used = detect.detect_markers_auto(front_img)
        markers_side,  _            = detect.detect_markers_auto(side_img)
    else:
        markers_front, colour_used = detect.detect_markers(front_img, cfg.colour)
        markers_side,  _            = detect.detect_markers(side_img, cfg.colour)

    result.colour_detected = colour_used
    if len(markers_front) == 0:
        raise RuntimeError(f"MARKER_DETECTION_FAILED: no markers found using {colour_used}. "
                           "Check lighting, marker colour, and DSV placement.")
    if len(markers_side) == 0:
        result.warnings.append("Side view: no markers detected — side measurements skipped")

    # -------------------------------------------------------------------------
    # Stage 4 — Labelling
    # -------------------------------------------------------------------------
    front_result = label.label_front(markers_front, x_mid, marker_diam_px, mm_per_px)
    side_result  = label.label_side(markers_side, mm_per_px)

    # Cross-validate front vs side levels
    front_result = label.cross_validate_levels(front_result, side_result)

    result.front_labels = front_result.labels
    result.side_labels  = side_result.side_labels
    result.flags.extend(front_result.flags)
    result.flags.extend(side_result.side_flags)
    result.warnings.extend(front_result.warnings)
    result.warnings.extend(side_result.side_warnings)

    # -------------------------------------------------------------------------
    # Stage 5 — Measurement computation
    # -------------------------------------------------------------------------
    measurements = measure.compute_measurements(
        front_result.labels, side_result.side_labels, mm_per_px, human_reads
    )
    result.measurements = measure.measurements_to_dict(measurements)

    # Collect flags and warnings from measurement stage
    result.flags.extend(measurements.flags)
    result.warnings.extend(measurements.warnings)

    # -------------------------------------------------------------------------
    # Stage 6 — Quality gates + read-confirm
    # -------------------------------------------------------------------------
    # Check agree if human reads provided
    if human_reads:
        app_reads = {name: m["value"] for name, m in result.measurements.items()}
        agree_r = confirm.check_agree(human_reads, app_reads, cfg.agree_threshold_mm)
        result.agree_results = agree_r
        for name, r in agree_r.items():
            if not r["agree"]:
                result.warnings.append(
                    f"{name}: human={r['human']:.0f}cm, app={r['app']:.0f}cm, "
                    f"Δ={r['delta_mm']}mm > {cfg.agree_threshold_mm}mm threshold"
                )

    # -------------------------------------------------------------------------
    # Stage 7 — Output
    # -------------------------------------------------------------------------
    result.processing_time_ms = round((time.time() - t0) * 1000, 1)

    # Landmarks
    result.landmarks_px = measure.landmarks_to_dict(
        front_result.labels, side_result.side_labels
    )

    # Save overlays
    result.save_overlays(out_dir)

    # Write JSON
    result.write_json(out_dir / "measurement.json")

    return result


def run_batch(captures: list[dict], out_dir: pathlib.Path | str,
              config: PipelineConfig | None = None) -> list[PipelineResult]:
    """
    Run pipeline on multiple captures.

    Args:
        captures: list of dicts with keys: front_path, side_path, human_reads, capture_id
        out_dir: root output directory (creates subdirs per capture_id)
    """
    out_dir = pathlib.Path(out_dir)
    results = []
    for cap in captures:
        cid = cap.get("capture_id", f"cap_{len(results)}")
        cap_dir = out_dir / cid
        cap_dir.mkdir(parents=True, exist_ok=True)
        r = run(
            pathlib.Path(cap["front_path"]),
            pathlib.Path(cap["side_path"]),
            human_reads=cap.get("human_reads"),
            out_dir=cap_dir,
            config=config,
        )
        results.append(r)
    return results