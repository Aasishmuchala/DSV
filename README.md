# DSV — Disposable Sizing Vest

**Build status:** 12/12 tests passing ✓  
**Generated:** `svg/marker_sheet.svg` (5KB) · `svg/ruler_strip.svg` · `svg/cutting_guide.svg`

DSV is a printed-tape body measurement system for residential construction-QC use in India. One-size-fits-all, disposable, ≤ ₹40/kit.

---

## Quick start

```bash
cd C:/Users/aasis/AppData/Local/hermes/claude-code/dsv

# Run tests
python -m pytest dsv/tests/synthetic_test.py dsv/tests/edge_case_test.py -v

# Run the web UI (photo upload + results display)
python server.py   # opens http://localhost:5000

# Generate the marker sheet
python -m dsv.marker_sheet

# Run the pipeline on a pair of photos (Python API)
from dsv.pipeline import run
result = run("front.jpg", "side.jpg", out_dir="results/")
```

---

## What it does

1. **Customer** places the printed DSV vest, wraps 4 adhesive strips (bust, underbust, waist, hip) around their body, and reads the number where the strip overlaps the printed scale.
2. **App** takes front + side phone photos of the vest-wearing customer.
3. Pipeline detects neon green markers → labels body landmarks → computes measurements → confirms against customer read.

---

## Architecture

```
dsv/
├── ingest.py        EXIF-preserving image load, HEIC→RGB, resize
├── scale.py         strip detection + tick-based mm/px calibration
├── detect.py        HSV colour segmentation for marker blobs
├── label.py        geometric labelling (front + side), count checks
├── measure.py       linear distances + Ramanujan ellipse girths
├── confirm.py       human-vs-app quality gates
├── pipeline.py      orchestrator — JSON + annotated overlay output
├── marker_sheet.py  programmatic SVG generation
└── tests/
    ├── synthetic_test.py   6 regression tests
    └── edge_case_test.py   5 edge case tests
```

`result.measurements` keys: `across_shoulder_mm`, `shoulder_slope_deg`, `front_length_mm`, `bust_girth_mm`, `underbust_girth_mm`, `waist_girth_mm`, `hip_girth_mm`.

Output: `results/measurement.json` + `results/annotated_front.jpg` + `results/annotated_side.jpg`.

---

## Measurement agreement threshold

v0 pilot: **±20 mm** between customer read and app read.

---

## Marker spec

| Property | Value |
|---|---|
| Colour | neon green `#00FF00` |
| Diameter | 15–18 mm |
| Centre strip tick spacing | 40.0 mm |
| Band strip tick spacing | 25.0 mm |
| Print tolerance | ±0.2 mm per batch per run |

HSV detection range for green: `(36, 100, 70)` – `(85, 255, 255)`.

---

## Generate printable marker sheet

```bash
python -m dsv.marker_sheet
```

Outputs to `svg/`:
- `marker_sheet.svg` — full A4 landscape (4 band strips + ruler)
- `ruler_strip.svg` — ruler strip only (1/3 A4 portrait)
- `cutting_guide.svg` — cutting guide for adhesive sheet

**Print at 100% scale** — no fit-to-page. Verify first-run accuracy with calipers.

---

## Key implementation decisions

1. **Shoulder row detection** uses top-2 side markers by y-position (not top-y of all markers) to avoid cf_neck interference
2. **MIDLINE_THRESH_DIAM = 0.8** — HPS at ~60px from x_mid are NOT treated as midline; they appear in side markers for shoulder row detection
3. **Missing marker** → flag + assign extremes as tips + inner as HPS. No guessing. Measurement skipped gracefully.
4. **Measurement agreement threshold: 20 mm** for v0 pilot
5. **Print accuracy: ±0.2 mm** — verify with calipers on first run of every print batch

---

## Dashboard

Project 2 at `http://localhost:7321` — DSV namespace.

Full spec: `SPEC.md`.  
Build plan: `PLAN.md`.