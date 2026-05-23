# DSV — Disposable Sizing Vest
## Product Specification v1.0 (post stress-test review)

**Version:** v1.0
**Form:** Read-Confirm DSV — printed-tape vest with dual human + app readout
**Owner:** solo founder build until first hire
**Goal:** everything needed to build, test, and pilot without further design decisions.

---

## 0. What the DSV is, and its role

A cheap, disposable, printed-tape "vest" (not sewn fabric) that the customer wears
to take two phone photos. It carries high-contrast markers at known body points and
printed cm scales, so the app extracts measurements — and the customer reads key
measurements herself and the app confirms them (dual readout catches silent errors).

**Strategic role:** the DSV is the *fit-safe, solo-buildable first instrument*
and the *labelled-data generator* for the later vest-free product.

**Runs in parallel (non-negotiable):** demand validation. Validate with real
customers (concierge hand-measuring) while building. The build is gated on demand,
not the reverse.

---

## 1. Design goals & non-goals

**Goals**
- One product fits all body sizes (no S/M/L manufacturing).
- Disposable, flat-mailable, cheap (target ≤ ₹40/kit incl. envelope).
- Scale baked in (no separate checkerboard / reference object).
- Dual readout: customer reads girths; app confirms; divergence flagged.
- Buildable solo with OpenCV; no ML training required for v0.

**Non-goals (v0)**
- Armhole, dart, neckline-depth (need 3D / multi-view — out of scope).
- Sub-cm girth accuracy (physics-limited by 2-photo ellipse).
- Fully automated trust (human-in-the-loop on first order per customer).
- Loose-clothing capture (require fitted/minimal clothing at capture).

---

## 2. Physical specification

### 2.1 Components (one connected printed-tape piece)

1. **Shoulder straps + light back yoke** — drape over both shoulders; carry
   shoulder-tip and HPS markers; hold the centre panel positioned.
2. **Centre ruler panel (vertical)** — ~20 mm wide, ~320 mm long, runs neck →
   below waist down the front. Printed cm scale. Carries centre-front markers
   (neck, underbust, waist). Doubles as the vertical length reference + scale source.
3. **Wrap-and-read bands (4):** bust, underbust, waist, hip — ~15 mm tall printed
   measuring tapes attached to the centre panel at each level. Wrap around the
   body, overlap, and show a readable circumference at the closure point.

### 2.2 Materials
- **Substrate:** paper-backed measuring-tape stock or non-woven adhesive tape
  (the material disposable tailor's tapes use). Pennies/metre.
- **Adhesive:** acrylic-based repositionable adhesive tape (Post-it / medical
  skin tape grade). Skin-safe (hypoallergenic acrylic, ISO 10993 tested).
  **Supplier:** order sample packs from 3M India or Avera before bulk buy.
- **Band fastener:** adhesive tab at the free end (simplest to prototype, allows
  overlap adjustment). Test slot-and-tab in pilot.

### 2.3 Markers

**Shape/size:** filled circles, **15–18 mm** diameter.

**Colour:** **neon green (#00FF00)** default.
Rationale: Red overlaps with common Indian clothing (burgundy, maroon, skin under
warm light). Green is rare in Indian clothing palettes, sits in the complementary
HSV channel (more stable under mixed lighting), and is easier to isolate via HSV
segmentation than red which wraps the hue wheel.

HSV range for green detection: `(36, 100, 70)` – `(85, 255, 255)`.
Test alternatives: cyan `(90, 100, 70)` – `(140, 255, 255)`.
If all colours fail under a specific lighting, fall back to high-saturation
monochrome (ignore hue, only S > 150, V > 100).

**Body-landmark markers (front, 12):**
- sh_tip_L, hps_L, hps_R, sh_tip_R (shoulder row — sorted by x, not y)
- cf_neck, cf_underbust, cf_waist, cf_hip (centre-front, one per band)
- bust_L, bust_R, underbust_L, underbust_R, waist_L, waist_R, hip_L, hip_R

**Body-landmark markers (side, 5):**
- sh_tip_side, bust_side, underbust_side, waist_side, hip_side

### 2.4 Scale (baked in — critical)
- **Centre strip:** marker/tick centres at **40.0 mm**.
- **Bands:** tick centres at **25.0 mm**.
- App derives mm-per-pixel from the pixel distance between two adjacent known-spacing
  ticks. No checkerboard, no credit card, no A4.
- **Print accuracy requirement:** verify printed spacing with calipers on the first
  run of every print batch; tolerance **±0.2 mm**. Printers rescale — an off-scale
  print silently corrupts every measurement.

### 2.5 Read points
Each band shows a number where its free end crosses the printed scale at overlap.
A printed thin horizontal guide line runs along each band so the customer keeps it level.

### 2.6 Cost target
≤ ₹40 per kit including envelope and instruction card. One A4-equivalent sheet of
tape stock yields one full applicator set.

---

## 3. Capture protocol (what the customer does)

1. **Environment:** plain **light wall** behind; even lighting; no harsh shadows.
   App enforces this (pre-capture check). Capture environment test:
   - Check wall region is uniformly light (stddev of grayscale < threshold)
   - If wall check fails, prompt user to move to a lighter/neutral background
2. **Clothing:** fitted or minimal. Loose clothing is rejected by the app (§5.6).
   State this explicitly in instructions.
3. **Apply DSV:** straps over shoulders, centre dot at throat hollow, strip straight
   down centre; wrap bust band at fullest bust (level), underbust directly under,
   waist at narrowest, hip band at fullest hip. Read each band number.
4. **Phone:** at **chest height**, ~**2 m** away, held **level**, portrait.
   Use a timer or helper. (Front camera + mirror acceptable if framing OK.)
5. **Breathing:** capture at **end-exhale** — "breathe out fully, hold, then capture."
   Enforced in app (countdown prompt).
6. **Photos:** front + side. (No separate calibration photo — scale is in the strip.)
7. **App confirm:** app shows its read vs the customer's read per band; confirm or retake.
8. **Done:** peel off, bin (or keep for reorder — measurements are stored).

---

## 4. Measurements & output

### 4.1 Measurement list (v0)
| Name | Type | Source |
|---|---|---|
| across_shoulder | linear | sh_tip_L ↔ sh_tip_R |
| shoulder_slope | angle | hps_R → sh_tip_R |
| front_length | linear (y-only) | hps_R → cf_waist |
| bust_girth | girth | bust_L↔bust_R width + bust_side depth |
| underbust_girth | girth | underbust_L↔underbust_R width + underbust_side depth |
| waist_girth | girth | waist_L↔waist_R width + waist_side depth |
| hip_girth | girth | hip_L↔hip_R width + hip_side depth |

### 4.2 Output JSON schema
```json
{
  "schema_version": "dsv-1.0",
  "scale_mm_per_px": 0.0,
  "measurements": {
    "across_shoulder_mm": {"value": 0.0, "confidence": "high|med|low",
                           "human_read_mm": null, "app_read_mm": 0.0,
                           "agree": true},
    "bust_girth_mm":      {"value": 0.0, "confidence": "...",
                           "human_read_mm": 0.0, "app_read_mm": 0.0,
                           "agree": true},
    "underbust_girth_mm": {"value": 0.0, "confidence": "...",
                           "human_read_mm": 0.0, "app_read_mm": 0.0,
                           "agree": true},
    "waist_girth_mm":     {"value": 0.0, "confidence": "...",
                           "human_read_mm": 0.0, "app_read_mm": 0.0,
                           "agree": true},
    "hip_girth_mm":       {"value": 0.0, "confidence": "...",
                           "human_read_mm": 0.0, "app_read_mm": 0.0,
                           "agree": true}
  },
  "landmarks_px": {"sh_tip_L": [x, y], "...": [0, 0]},
  "flags": ["waist_band_tilted", "loose_clothing_suspected", "LEVEL_MISMATCH", "MISSING_MARKER"],
  "warnings": []
}
```

Annotated overlays: PNG, burned-in labels + measurement lines, full resolution
(~200KB per image at 2000px longest edge). Stored with each capture.

---

## 5. Measurement pipeline — tech spec

Language/stack: **Python 3.11, OpenCV, NumPy.** No ML required for v0
(geometry + classical CV). Optional later: trained marker detector (YOLO/RT-DETR).

### 5.1 Stage 1 — Ingest & preprocess
- Honour EXIF orientation; convert HEIC→JPG if needed.
- Resize longest edge to ~2000 px for speed (keep scale factor).
- Optional lens-undistort if a phone profile is available (skip v0).

### 5.2 Stage 2 — Scale calibration
- Detect the printed scale ticks on the centre strip (or any band).
- Take two adjacent ticks of known spacing (40 mm strip / 25 mm band).
- `mm_per_px = known_spacing_mm / pixel_distance`.
- Use the median over several adjacent pairs for robustness.
- **Fail loudly** if ticks not found — never silently fall back.

### 5.3 Stage 3 — Marker detection
- Colour segment in HSV (green range below). Morphological open+close.
- Contour filter: area ∈ [60, 3000] px², circularity ≥ 0.55.
- Output marker centroids + radii.

HSV_GREEN = `(36, 100, 70)` – `(85, 255, 255)` (default)
HSV_CYAN = `(90, 100, 70)` – `(140, 255, 255)` (alternative)
HSV_FALLBACK = S > 150, V > 100 (monochrome high-sat, ignores hue)

**Robustness note:** Phase 0 colour test is load-bearing. Test under 3 lighting
conditions before finalizing HSV ranges:
1. Warm white LED, 2700K (common Indian home lighting)
2. Natural daylight from window
3. Cool white LED, 4000K (offices, malls)

### 5.4 Stage 4 — Labelling (robust to slouch + missing markers)

**FRONT VIEW — shoulder row (4 markers):**
1. Exclude midline markers: any marker within 2× marker_diameter of x-midline
   is excluded from shoulder/hip row processing. (midline markers = cf_neck,
   cf_underbust, cf_waist, cf_hip.)
2. From remaining markers, identify the shoulder row by: top-most cluster of
   markers within a y-band of ≤ marker_diameter spread.
3. Sort shoulder row by x — leftmost = sh_tip_L, next = hps_L, next = hps_R,
   rightmost = sh_tip_R. **This is x-sort, NOT y-sort** (fixes slouch failure).
4. Count check: if len(shoulder_row) ≠ 4 → emit `MISSING_MARKER: shoulder_row`
   with count, skip dependent measurements.

**FRONT VIEW — HPS pair:**
- hps_L and hps_R are the two markers closest to x-midline in the upper body
  (above bust markers). Separate from shoulder tips by x-distance from centre.

**FRONT VIEW — cf_* centre markers:**
- These are the single markers closest to x-midline at each band level.
- Validate: cf_neck.y must be above bust_L.y and below hps_R.y.
- Validate: cf_waist.y must be between bust and hip.
- If bounds violated → emit `LABEL_UNCERTAIN: cf_*` with position, still compute.

**FRONT VIEW — side pair markers (bust_L/R, underbust_L/R, waist_L/R, hip_L/R):**
1. Exclude midline (within 2× marker_diameter of x-midline).
2. Split into left (x < x-midline) and right (x > x-midline).
3. At each band level: the leftmost pair = *_L, rightmost pair = *_R.
4. Validate band-level heights: |y(bust_L) - y(bust_R)| < tolerance_px; if
   exceeded → emit `LEVEL_MISMATCH: bust` and degrade confidence.

**SIDE VIEW — 5 markers, sorted by y:**
1. Sort all detected markers by y (ascending).
2. Sanity check: y-span must be ≥ 200px for a human torso; if not → flag
   `SIDE_VIEW_INVALID: y_span_too_narrow`.
3. Map by y-position relative to expected body proportions:
   - top marker → sh_tip_side (must be in top 20% of span)
   - next → bust_side (must be in bust region)
   - next → underbust_side
   - next → waist_side
   - bottom → hip_side
4. Validate: bust_side.y should match the average of bust_L.y + bust_R.y from
   the front view within tolerance_px (same-level enforcement). If not → emit
   `LEVEL_MISMATCH: bust_front_vs_side`.
5. Count check: if len(side_markers) ≠ 5 → emit `MISSING_MARKER: side_row`
   with count, skip dependent measurements.

### 5.5 Stage 5 — Measurement computation
- Linear: `hypot(dx, dy) * scale`.
- front_length: **y-difference only** (`abs(dy) * scale`), not diagonal.
- shoulder_slope: `degrees(atan2(dy, dx))`.
- Girth (ellipse, Ramanujan): front width = *_L ↔ *_R; side depth = silhouette
  width at *_side.y; `a=width/2, b=depth/2`,
  `P ≈ π(a+b)(1 + 3h/(10+√(4-3h)))`, `h=((a-b)/(a+b))²`.
- Side silhouette: threshold light wall (`THRESH_BINARY_INV ~200`). Requires
  plain light wall — enforce in capture app pre-check. Morphological open,
  measure dark span at the band's y.
- **Same-level rule:** front markers and side markers at each band must agree
  in y within tolerance_px. Enforced algorithmically (see Stage 4).

**Loose-clothing detection algorithm:**
- Compute body outline from front silhouette (body pixels vs wall pixels).
- At each band, compute the angle of the body outline tangent at the band level.
- If the band deviates from the body outline by > ~15° at any point → flag
  `loose_clothing_suspected`.
- Alternative: if the distance from band markers to body outline is consistently
  > marker_diameter → flag. Both methods can run in parallel.

### 5.6 Stage 6 — Read-confirm & quality gates
- Compare `human_read` vs `app_read` per girth; **`agree = |Δ| ≤ 20 mm`** (tightened
  from 10mm after stress-test: a 1° band twist at r=50cm = ~17mm error; 10mm
  threshold too strict for real captures; calibrate to 15mm after pilot data).
- On disagreement: flag, prompt retake or manual confirm; store both.
- **Loose-clothing gate:** fire as above.
- **Band tilt gate:** detect band tick line deviation from horizontal; flag if > 3°.
- **Level mismatch gate:** fire on front/side y-spread > tolerance_px.
- **Missing marker gate:** fire on count mismatch at any row.

### 5.7 Stage 7 — Output
- Write JSON (§4.2), annotated overlays (PNG, burned-in labels + lines),
  and a per-capture log row.

---

## 6. Accuracy targets & error budget

| Measurement | Target | Dominant error sources |
|---|---|---|
| Linear (shoulder, lengths) | ±3–5 mm | placement, detection centroid |
| Shoulder slope | ±1–2° | placement |
| Girth (bust/underbust/waist/hip) | ±10–15 mm | ellipse approx, breathing, scale-plane, placement |

**Known unsolved at v0:** breathing (mitigated by end-exhale capture), single-plane
scale error, ellipse vs true cross-section (systematically overestimates flatter
cross-sections), loose clothing (rejected, not solved).

---

## 7. Software architecture & repo

```
dsv/
  ingest.py        # EXIF, HEIC, resize
  scale.py         # tick-spacing scale
  detect.py        # HSV marker detection
  label.py         # geometric labelling (front, side) — stress-test hardened
  measure.py       # distances, angles, ellipse girth
  confirm.py       # human-vs-app reconcile, quality gates
  pipeline.py      # orchestrates, emits JSON + overlays
  tests/
    synthetic_test.py   # known-geometry regression (MUST pass before real use)
    edge_case_test.py   # slouch, missing markers, tilted bands (Phase 0 DoD)
  README.md
```

**Testing discipline (hard rule):** `synthetic_test.py` with known-geometry
inputs must pass before trusting any real measurement. `edge_case_test.py`
covers slouch, missing marker, level mismatch — must also pass before real use.

**Pilot (later):** thin capture app (Flutter / React Native) → uploads to a
Python service (FastAPI) running the same package → returns JSON + overlays for
the confirm screen. Stateless workers; queue if volume grows.

---

## 8. Build phases, milestones & definition of done

### Phase 0 — Hand-made prototype + first test (this week)
- [ ] Print marker + scale sheet on label/tape stock; verify spacing with
      calipers (±0.2 mm). Order sample adhesive tape stock first.
- [ ] Cut the centre strip, straps, 4 bands; assemble one DSV in your size.
- [ ] **Colour test (non-negotiable):** print green, cyan, red markers; photograph
      under 3 lighting conditions; segment and confirm detection rate > 95% per colour.
      Finalise HSV ranges from this data.
- [ ] Run `synthetic_test.py` green.
- [ ] Run `edge_case_test.py` covering: (a) slouch simulated by marker shift,
      (b) one missing marker, (c) band tilt > 3°, (d) level mismatch front vs side.
- [ ] Capture self + 2 volunteers; tape-measure ground truth.
- [ ] Capture with deliberately mis-placed DSV (off-centre, wrong band heights);
      confirm pipeline flags errors and degrades gracefully.
- [ ] Compare three conditions: loose stickers vs DSV vs tailor's tape.
- [ ] Log all error numbers per measurement for self-applied DSV.
- **DoD:** Phase 0 test gates this before any print run. Error numbers documented.
  Colour test complete with HSV ranges locked.

### Phase 1 — Pipeline hardening
- [ ] Tune detection to final marker colour under 3 lighting conditions.
- [ ] Labelling robust to missing/extra marker (degrades, never guesses).
- [ ] Quality gates (loose clothing, band tilt, same-level, missing marker)
      firing correctly on real captures.
- [ ] Overlay rendering: landmark labels + measurement lines visible and accurate.
- **DoD:** pipeline runs end-to-end on 5+ real captures with honest flags.

### Phase 2 — Capture + confirm app
- [ ] Guided capture (end-exhale prompt, framing guide, levelness check, wall check).
- [ ] Confirm screen: app read vs human read, retake on divergence (≥ 20mm Δ).
- **DoD:** a non-technical person completes capture unaided and gets a result.

### Phase 3 — Pilot with real customers
- [ ] 5–10 real customers; human-checked first blouse; log fit outcomes.
- [ ] Every capture stored (photos + GT + extracted + confirm + fit result).
- [ ] Calibrate agree threshold from real Δ distribution.
- **DoD:** measured reorder/fit-acceptance rate; dataset for the vest-free build.

---

## 9. Resolved decisions log

| Decision | Choice | Rationale |
|---|---|---|
| Marker colour | **Neon green** (#00FF00) default; cyan alternative; red last resort | Red overlaps with common clothing; green rare in Indian palettes; more stable HSV segmentation |
| Underbust front markers | **Include in v0** (underbust_L, underbust_R, cf_underbust) | Zero incremental cost; richer dataset for blouse fitting + vest-free build |
| Adhesive type | **Acrylic repositionable** (Post-it / medical tape grade, ISO 10993) | Repositionable, skin-safe, available from 3M India / Avera; test samples before bulk |
| Band fastener | **Adhesive tab** for v0; test slot-and-tab in pilot | Simplest to prototype; slot-and-tab requires die-cutting, test in Phase 3 |
| Agree threshold | **20 mm** (calibrate to 15mm after pilot data) | 1° twist at r=50cm = ~17mm; 10mm too strict for real captures |
| Midline exclusion threshold | **2 × marker_diameter** from x-midline | Empirically covers typical marker placement variation |
| Phase 0 colour test | **3 lights:** warm 2700K LED, daylight, cool 4000K LED | Covers Indian home + office + outdoor environments |
| Overlay format | **PNG, burned-in, full resolution** (~200KB at 2000px) | Simple contract; no layer parsing needed |

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Self-placement error too large | Phase 0 test gates this before any print run |
| Silent wrong numbers | synthetic_test + edge_case_test + dual readout + confidence flags |
| Band tilt → wrong girth | guide line + app levelness gate (> 3° flagged) |
| Loose clothing | reject at capture; require fitted/minimal; algorithm in §5.5 |
| Print scale drift | caliper-verify every batch (±0.2 mm) |
| Marker colour clashes with clothing | colour test in Phase 0; neon green default (low clothing overlap) |
| Breathing noise | end-exhale capture enforced in app |
| No customer demand | concierge validation in parallel — overrides everything |
| Labelling collapses on slouch | x-position sort, not y-order; count check before labelling |
| Missing marker silently shifts all labels | count-and-compare; `MISSING_MARKER` flag; skip dependent measurements |
| Side view mislabelled (missing marker shifts all) | y-span sanity check; front/side level cross-validation |
| Light wall not plain | pre-capture wall uniformity check in app; enforce or prompt |

---

## 11. The one rule above all

**Validate before you optimise.** The DSV exists to (a) protect the first-fit
and (b) generate labelled data while you confirm demand. If the Phase 0 test
shows self-placement error is too large, or concierge validation shows no demand,
stop and rethink — do not keep refining the instrument. A measured "no" found
cheaply is the most valuable result this plan can produce.