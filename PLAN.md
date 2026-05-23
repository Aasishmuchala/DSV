# DSV Build Plan

## Phase 0 — Prototype + First Test

### 0.1 — Source materials

- [ ] Order sample adhesive tape stock (paper-backed measuring tape or non-woven)
- [ ] Order 3M Scotch tape / Post-it adhesive samples for skin-safe testing
- [ ] Source calipers (digital, 0.1mm resolution minimum)

### 0.2 — Print prototype sheet

- [ ] Design marker + scale sheet in vector (Inkscape or Canva)
- [ ] Print on label stock / tape stock
- [ ] Verify tick spacing with calipers: ±0.2 mm tolerance per tick pair
- [ ] Test green, cyan, red markers on one sheet (colour test prep)

### 0.3 — Assemble first DSV

- [ ] Cut centre strip (~20mm × 320mm)
- [ ] Cut 4 wrap bands (bust, underbust, waist, hip) with adhesive tabs
- [ ] Assemble straps + back yoke (hand-cut, not printed)
- [ ] Apply to self — check fit, adhesion, comfort

### 0.4 — Colour test (non-negotiable gate)

- [ ] Photograph green, cyan, red markers under: warm 2700K LED, daylight, cool 4000K LED
- [ ] Run detection on each image — record detection rate % per colour per lighting
- [ ] If no colour hits > 95% detection → try monochrome fallback (S > 150, V > 100)
- [ ] Lock HSV ranges; document in SPEC.md §2.3
- [ ] **Gate:** HSV ranges locked before Stage 1 proceeds

### 0.5 — Synthetic test (known-geometry regression)

- [ ] Write synthetic_test.py: render known-geometry marker set, run full pipeline
- [ ] Verify: scale_calibration passes, all measurements within 0.1mm of expected
- [ ] **Gate:** synthetic_test.py must be 100% green before any real photo is processed

### 0.6 — Edge case test suite

- [ ] Write edge_case_test.py:
  - [ ] (a) slouch: shift hps markers 30px downward, verify x-sort correctly identifies shoulder row
  - [ ] (b) missing marker: remove one shoulder marker, verify MISSING_MARKER flag fires
  - [ ] (c) band tilt: simulate 5° rotation, verify band_tilt flag fires
  - [ ] (d) level mismatch: shift bust_side 20px, verify LEVEL_MISMATCH fires
  - [ ] (e) loose clothing: add 25px padding to body outline, verify loose_clothing_suspected fires
- [ ] **Gate:** all edge cases degrade gracefully, no silent wrong outputs

### 0.7 — Real captures: self + 2 volunteers

- [ ] Capture self with DSV + fitted clothing, end-exhale, plain wall
- [ ] Capture 2 volunteers (same protocol)
- [ ] Record ground truth: tailor's tape measurements by a second person
- [ ] Capture with deliberately mis-placed DSV (off-centre, wrong band heights)
- [ ] Run all captures through pipeline
- [ ] Document error per measurement vs ground truth
- [ ] Log all failures, flags, and degraded outputs
- **DoD:** Phase 0 error numbers documented; all quality gates firing; colour test locked

---

## Phase 1 — Pipeline Hardening

- [ ] Integrate locked HSV ranges from Phase 0 into detect.py
- [ ] Add wall uniformity pre-check (stddev of grayscale in wall region)
- [ ] Add loose-clothing detection algorithm (body outline vs band position)
- [ ] Add side silhouette width extraction with morphological open
- [ ] Verify labelling: run on all Phase 0 real captures
- [ ] Add overlay rendering (annotated PNG with landmark labels + measurement lines)
- [ ] Add per-capture log row output
- [ ] Run on 5+ real captures; all quality gates firing correctly
- **DoD:** end-to-end pipeline on 5+ real captures with honest flags and overlays

---

## Phase 2 — Capture + Confirm App

- [ ] Design guided capture flow: wall check → apply DSV → levelness check → countdown → capture front → capture side
- [ ] End-exhale prompt: visual countdown + audio cue
- [ ] Phone levelness check (accelerometer via React Native / Flutter)
- [ ] Confirm screen: app read vs human read per girth, ≥ 20mm Δ → retake or manual override
- [ ] Store: both photos + overlay + JSON + human_read per capture
- [ ] Test with one non-technical person (no coaching)
- **DoD:** non-technical person completes capture unaided and gets a result

---

## Phase 3 — Pilot with Real Customers

- [ ] Recruit 5–10 real customers (blouse fitting use case)
- [ ] Each capture: DSV photo + human tape-measure GT + fit outcome (first blouse made)
- [ ] Log: photos + GT + extracted + confirm + fit result
- [ ] Analyse Δ distribution: what is the real agree threshold?
- [ ] Calculate: measured reorder / fit-acceptance rate
- [ ] Identify: which body types / measurements are most error-prone
- **DoD:** measured fit-acceptance rate; dataset ready for vest-free build; all captures stored with full provenance