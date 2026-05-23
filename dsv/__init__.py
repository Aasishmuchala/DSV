"""
DSV — Disposable Sizing Vest measurement pipeline.
"""
from dsv import (
    confirm,
    detect,
    ingest,
    label,
    measure,
    pipeline,
    scale,
    marker_sheet,
)
from dsv.pipeline import PipelineConfig, PipelineResult, run, run_batch
from dsv.scale import calibrate_scale_from_strip, detect_scale_region, detect_ticks_on_strip
from dsv.label import LabelResult, cross_validate_levels
from dsv.measure import Measurement, AllMeasurements

__version__ = "0.1.0"
__all__ = [
    "confirm", "detect", "ingest", "label", "measure", "pipeline", "scale",
    "marker_sheet", "PipelineConfig", "PipelineResult", "run", "run_batch",
    "calibrate_scale_from_strip", "detect_scale_region", "detect_ticks_on_strip",
    "LabelResult", "cross_validate_levels", "Measurement", "AllMeasurements",
]