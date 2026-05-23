"""
DSV marker sheet — printable SVG for adhesive tape stock.

Generates two files:
  dsv/svg/marker_sheet.svg   — full sheet (4 band strips + ruler)
  dsv/svg/ruler_strip.svg    — ruler strip only (1/3 A4 portrait)

Run:
  python -m dsv.marker_sheet

Print at 100% scale (no fit-to-page). Verify with calipers:
  Centre strip tick spacing: 40.0mm  (tolerance ±0.2mm)
  Band strip tick spacing:  25.0mm  (tolerance ±0.2mm)
"""
from __future__ import annotations

import sys, pathlib

# ── colours ──────────────────────────────────────────────────────────────────
NEON_GREEN  = "#00FF00"
TICK_COLOUR = "#1a1a1a"   # near-black tick marks
STRIP_BG    = "#f5f5f5"   # light strip background

# ── dimensions (A4 landscape, mm) ─────────────────────────────────────────────
A4_W = 297.0
A4_H = 210.0

# Strip widths (mm)
BAND_W   = 20.0   # band strip width
RULER_W  = 16.0   # ruler strip width (narrower, just the scale)

# Tick spacings (mm) — MUST match pipeline's known_spacing_mm values
BAND_SPACING  = 25.0   # mm between tick centres
RULER_SPACING = 40.0   # mm between tick centres

# Marker diameter (mm) — must be 15–18mm per spec
MARKER_DIAM_MM = 16.0

# Margins
MARGIN_X = 10.0
MARGIN_Y = 8.0

# Band strip height — full A4 height minus margins
BAND_H = A4_H - 2 * MARGIN_Y   # 194mm — long enough to wrap overlapping around body

# Ruler strip — full A4 portrait height for maximum scale accuracy
RULER_H = A4_H                  # 210mm tall


# ── helpers ───────────────────────────────────────────────────────────────────
def mm(value: float) -> str:
    """Format mm value for SVG attribute."""
    return f"{value:.1f}"


def tick_positions(start_mm: float, spacing_mm: float, max_mm: float) -> list[float]:
    """Return centred y-positions of tick marks from start to max."""
    positions = []
    y = start_mm
    while y <= max_mm:
        positions.append(y)
        y += spacing_mm
    return positions


def make_marker(cx_mm: float, cy_mm: float, r_mm: float, colour: str) -> str:
    """SVG circle element for a filled marker."""
    return (f'<circle cx="{mm(cx_mm)}" cy="{mm(cy_mm)}" r="{mm(r_mm)}" '
            f'fill="{colour}" stroke="{colour}" stroke-width="0.3" />')


def make_tick(y_mm: float, strip_w_mm: float, h_mm: float = 1.0) -> str:
    """SVG vertical tick line centred on strip."""
    x = (strip_w_mm / 2)
    y1 = y_mm - h_mm / 2
    y2 = y_mm + h_mm / 2
    return f'<line x1="{mm(x)}" y1="{mm(y1)}" x2="{mm(x)}" y2="{mm(y2)}" ' \
           f'stroke="{TICK_COLOUR}" stroke-width="0.5" stroke-linecap="round" />'


def make_scale_numbers(y_mm: float, spacing_mm: float, x_mm: float) -> str:
    """SVG text labels for scale ticks."""
    value = round(y_mm / spacing_mm)
    return (f'<text x="{mm(x_mm + 2)}" y="{mm(y_mm + 1.2)}" '
            f'font-family="monospace" font-size="2.2" fill="#555">{value}</text>')


# ── band strip ───────────────────────────────────────────────────────────────
def build_band_strip(strip_w: float, strip_h: float, spacing: float,
                     y_start: float = 0.0) -> str:
    """SVG for a single measurement-band strip."""
    bg   = f'<rect x="0" y="0" width="{mm(strip_w)}" height="{mm(strip_h)}" ' \
           f'fill="{STRIP_BG}" stroke="#ccc" stroke-width="0.3" />'

    ticks = []
    nums  = []
    tick_y = y_start
    while tick_y <= strip_h:
        ticks.append(make_tick(tick_y, strip_w, h_mm=1.2))
        nums.append(make_scale_numbers(tick_y, spacing, strip_w))
        tick_y += spacing

    # Centre dashed guide line
    centre = strip_w / 2
    guide  = (f'<line x1="{mm(centre)}" y1="0" x2="{mm(centre)}" y2="{mm(strip_h)}" '
              f'stroke="#bbb" stroke-width="0.3" stroke-dasharray="1,1" />')

    return bg + guide + "".join(ticks) + "".join(nums)


# ── ruler strip ───────────────────────────────────────────────────────────────
def build_ruler_strip(strip_w: float, strip_h: float,
                      spacing: float = 40.0, y_start: float = 0.0) -> str:
    """SVG for the centre ruler strip."""
    bg   = f'<rect x="0" y="0" width="{mm(strip_w)}" height="{mm(strip_h)}" ' \
           f'fill="#e8e8e8" stroke="#aaa" stroke-width="0.3" />'

    ticks = []
    nums  = []
    tick_y = y_start
    counter = 0
    while tick_y <= strip_h:
        # Major tick every spacing, minor ticks in between
        ticks.append(make_tick(tick_y, strip_w, h_mm=2.0))
        nums.append(make_scale_numbers(tick_y, spacing, strip_w))
        tick_y += spacing
        counter += 1

    # Long centre line
    centre = strip_w / 2
    line = (f'<line x1="{mm(centre)}" y1="0" x2="{mm(centre)}" y2="{mm(strip_h)}" '
            f'stroke="#888" stroke-width="0.4" />')

    return bg + line + "".join(ticks) + "".join(nums)


# ── marker row (for cutting guide) ─────────────────────────────────────────────
def make_marker_row(marker_diam_mm: float, n_markers: int,
                    strip_w: float, y_mm: float, label: str) -> str:
    """Row of markers with a cutting guide label."""
    r   = marker_diam_mm / 2
    gap = 5.0
    total_w = n_markers * marker_diam_mm + (n_markers - 1) * gap
    start_x = (strip_w - total_w) / 2 + r

    circles = []
    for i in range(n_markers):
        cx = start_x + i * (marker_diam_mm + gap)
        circles.append(make_marker(cx, y_mm, r, NEON_GREEN))

    label_el = (f'<text x="{mm(strip_w/2)}" y="{mm(y_mm + r + 4)}" '
                f'text-anchor="middle" font-family="sans-serif" font-size="2.5" '
                f'fill="#333">{label}</text>')

    return "".join(circles) + label_el


# ── body placement diagram ───────────────────────────────────────────────────
def _build_body_placement_diagram(bx: float, by: float, bw: float, bh: float) -> str:
    """
    Simplified human body silhouette (front view) with marker placement labels.
    Shows where to position each band strip and individual marker dots.
    bx, by: top-left of the diagram area in mm
    bw, bh:  width and height of the diagram area in mm
    """
    # Body proportions (normalised, 0-1)
    # Centred within the box
    cx = bx + bw / 2
    scale = min(bw * 0.5, bh * 0.9)  # body width relative to box
    head_r = scale * 0.14
    shoulder_w = scale * 0.55
    waist_w = scale * 0.30
    hip_w = scale * 0.42

    # Y positions (proportional body landmarks, 0=top 1=bottom)
    head_cy    = by + bh * 0.08
    neck_y     = by + bh * 0.17
    shoulder_y = by + bh * 0.22
    bust_y     = by + bh * 0.36
    underbust_y= by + bh * 0.44
    waist_y    = by + bh * 0.56
    hip_y      = by + bh * 0.72
    crotch_y   = by + bh * 0.88

    parts = [
        # ── Head (circle) ────────────────────────────────────────────
        f'<circle cx="{mm(cx)}" cy="{mm(head_cy)}" r="{mm(head_r)}" '
        f'fill="none" stroke="#888" stroke-width="0.4" />',
        # Neck line
        f'<line x1="{mm(cx)}" y1="{mm(head_cy + head_r)}" '
        f'x2="{mm(cx)}" y2="{mm(neck_y)}" '
        f'stroke="#888" stroke-width="0.4" />',

        # ── Shoulders (horizontal line) ────────────────────────────────
        f'<line x1="{mm(cx - shoulder_w/2)}" y1="{mm(shoulder_y)}" '
        f'x2="{mm(cx + shoulder_w/2)}" y2="{mm(shoulder_y)}" '
        f'stroke="#888" stroke-width="0.6" stroke-linecap="round" />',
        # HPS marker dots on shoulders
        f'<circle cx="{mm(cx - shoulder_w/2)}" cy="{mm(shoulder_y)}" r="2.5" fill="#00CC44" />',
        f'<circle cx="{mm(cx + shoulder_w/2)}" cy="{mm(shoulder_y)}" r="2.5" fill="#00CC44" />',
        f'<text x="{mm(cx - shoulder_w/2 - 3)}" y="{mm(shoulder_y - 4)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#333">L</text>',
        f'<text x="{mm(cx + shoulder_w/2 + 1)}" y="{mm(shoulder_y - 4)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#333">R</text>',
        f'<text x="{mm(cx)}" y="{mm(shoulder_y + 4)}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="2" fill="#888">hps_L / hps_R</text>',

        # ── Body outline (left & right sides, simplified) ──────────────
        # Left side
        f'<path d="M {mm(cx - shoulder_w/2)} {mm(shoulder_y)} '
        f'Q {mm(cx - shoulder_w/2 + 5)} {mm(bust_y)} '
        f'{mm(cx - waist_w/2)} {mm(waist_y)} '
        f'Q {mm(cx - hip_w/2 + 3)} {mm(hip_y)} '
        f'{mm(cx - hip_w/2)} {mm(crotch_y)}" '
        f'fill="none" stroke="#888" stroke-width="0.5" />',
        # Right side
        f'<path d="M {mm(cx + shoulder_w/2)} {mm(shoulder_y)} '
        f'Q {mm(cx + shoulder_w/2 - 5)} {mm(bust_y)} '
        f'{mm(cx + waist_w/2)} {mm(waist_y)} '
        f'Q {mm(cx + hip_w/2 - 3)} {mm(hip_y)} '
        f'{mm(cx + hip_w/2)} {mm(crotch_y)}" '
        f'fill="none" stroke="#888" stroke-width="0.5" />',

        # ── Girth band indicators (horizontal dashed lines) ───────────
        # bust
        f'<line x1="{mm(cx - shoulder_w/2)}" y1="{mm(bust_y)}" '
        f'x2="{mm(cx + shoulder_w/2)}" y2="{mm(bust_y)}" '
        f'stroke="#00AAFF" stroke-width="0.5" stroke-dasharray="1.5,1.5" />',
        f'<text x="{mm(cx + shoulder_w/2 + 2)}" y="{mm(bust_y + 1.5)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#0077CC">BUST</text>',
        # underbust
        f'<line x1="{mm(cx - shoulder_w/2 + 8)}" y1="{mm(underbust_y)}" '
        f'x2="{mm(cx + shoulder_w/2 - 8)}" y2="{mm(underbust_y)}" '
        f'stroke="#00AAFF" stroke-width="0.5" stroke-dasharray="1.5,1.5" />',
        f'<text x="{mm(cx + shoulder_w/2 + 2)}" y="{mm(underbust_y + 1.5)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#0077CC">UB</text>',
        # waist
        f'<line x1="{mm(cx - waist_w/2)}" y1="{mm(waist_y)}" '
        f'x2="{mm(cx + waist_w/2)}" y2="{mm(waist_y)}" '
        f'stroke="#00AAFF" stroke-width="0.5" stroke-dasharray="1.5,1.5" />',
        f'<text x="{mm(cx + waist_w/2 + 2)}" y="{mm(waist_y + 1.5)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#0077CC">WAIST</text>',
        # hip
        f'<line x1="{mm(cx - hip_w/2)}" y1="{mm(hip_y)}" '
        f'x2="{mm(cx + hip_w/2)}" y2="{mm(hip_y)}" '
        f'stroke="#00AAFF" stroke-width="0.5" stroke-dasharray="1.5,1.5" />',
        f'<text x="{mm(cx + hip_w/2 + 2)}" y="{mm(hip_y + 1.5)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#0077CC">HIP</text>',

        # ── Neck base marker ────────────────────────────────────────────
        f'<circle cx="{mm(cx)}" cy="{mm(neck_y + 3)}" r="2.5" fill="#FF6600" />',
        f'<text x="{mm(cx + 4)}" y="{mm(neck_y + 4.5)}" '
        f'font-family="sans-serif" font-size="2.2" fill="#CC5500">cf_neck</text>',

        # ── Hip point markers ───────────────────────────────────────────
        f'<circle cx="{mm(cx - hip_w/2 + 2)}" cy="{mm(hip_y)}" r="2.5" fill="#FF6600" />',
        f'<circle cx="{mm(cx + hip_w/2 - 2)}" cy="{mm(hip_y)}" r="2.5" fill="#FF6600" />',
        f'<text x="{mm(cx - hip_w/2 - 1)}" y="{mm(hip_y + 4.5)}" text-anchor="end" '
        f'font-family="sans-serif" font-size="2" fill="#CC5500">hip_L</text>',
        f'<text x="{mm(cx + hip_w/2 + 1)}" y="{mm(hip_y + 4.5)}" '
        f'font-family="sans-serif" font-size="2" fill="#CC5500">hip_R</text>',

        # ── Midline markers (sternum + navel region) ───────────────────
        f'<circle cx="{mm(cx)}" cy="{mm(bust_y + 5)}" r="1.5" fill="#FF00FF" />',
        f'<circle cx="{mm(cx)}" cy="{mm(waist_y)}" r="1.5" fill="#FF00FF" />',
        f'<text x="{mm(cx + 3)}" y="{mm(bust_y + 7)}" '
        f'font-family="sans-serif" font-size="2" fill="#AA00AA">cf_x</text>',
        f'<text x="{mm(cx + 3)}" y="{mm(waist_y + 1.5)}" '
        f'font-family="sans-serif" font-size="2" fill="#AA00AA">cf_waist</text>',
        # Midline dashed line
        f'<line x1="{mm(cx)}" y1="{mm(shoulder_y)}" '
        f'x2="{mm(cx)}" y2="{mm(crotch_y)}" '
        f'stroke="#FF00FF" stroke-width="0.3" stroke-dasharray="1,2" opacity="0.5" />',

        # ── Band strip labels (how to wrap) ────────────────────────────
        f'<text x="{mm(bx + bw/2)}" y="{mm(by + 3)}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="3" fill="#555" font-weight="bold">'
        f'PLACEMENT GUIDE</text>',
    ]

    return "<g>" + "".join(parts) + "</g>"


# ── full marker sheet ─────────────────────────────────────────────────────────
def build_marker_sheet(out_dir: pathlib.Path | None = None) -> dict:
    """
    Generate the full printable marker sheet.

    Layout (A4 landscape):
      ┌───────────────────────────────────────────────────────┐
      │ bust band strip (25mm tick spacing)                   │
      │ underbust band strip (25mm tick spacing)              │
      │ waist band strip (25mm tick spacing)                  │
      │ hip band strip (25mm tick spacing)                    │
      │ ruler strip (40mm tick spacing) + marker row          │
      └───────────────────────────────────────────────────────┘

    Returns dict with file paths and a SheetSpec summary.
    """
    if out_dir is None:
        out_dir = pathlib.Path(__file__).parent.parent / "svg"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Full sheet SVG ─────────────────────────────────────────────────────
    # Layout: A4 landscape (297 × 210mm)
    #   Row 1 (y=14): 4 band strips side-by-side, 20mm wide × 194mm tall each
    #          x: 10, 32, 54, 76mm — total occupies y=14→208mm (within page)
    #   Row 2 (y=216): ruler strip (16mm wide × 194mm tall) at left
    #   Row 3 (y=216): body placement diagram on right (x=96→287mm)
    #   Row 4 (y=416): marker row + instructions text
    #
    # Each band strip on the sheet is the PRINTED STRIP — user cuts and tapes
    # ends together to form a wrap. The strip length on sheet = A4 height minus
    # margins = 194mm, which wraps up to ~194mm circumference per strip.
    # For larger circumferences, user overlaps or uses multiple strips.

    strip_area_w = BAND_W * 4 + 3 * 2  # 86mm for 4 bands + 2mm gaps

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{A4_W}mm" height="{A4_H}mm" '
        f'viewBox="0 0 {A4_W} {A4_H}">',
        f'<rect width="{A4_W}" height="{A4_H}" fill="white"/>',
        f'<text x="{MARGIN_X}" y="{MARGIN_Y + 4}" font-family="sans-serif" '
        f'font-size="4" fill="#555">DSV Marker Sheet v1.0 — print at 100% (no fit)</text>',
        f'<text x="{A4_W - MARGIN_X}" y="{MARGIN_Y + 4}" text-anchor="end" '
        f'font-family="sans-serif" font-size="3" fill="#aaa">'
        f'check with calipers: bands 25mm ±0.2, ruler 40mm ±0.2</text>',
    ]

    # ── Row 1: 4 band strips side by side ──────────────────────────────────
    y_bands = MARGIN_Y + 6   # y=14mm

    band_strips = ["bust", "underbust", "waist", "hip"]
    for i, band_name in enumerate(band_strips):
        x_pos = MARGIN_X + i * (BAND_W + 2)   # 2mm gap between columns
        inner = build_band_strip(BAND_W, BAND_H, BAND_SPACING, y_start=5.0)
        svg_parts.append(
            f'<g transform="translate({mm(x_pos)},{mm(y_bands)})">'
            f'<text x="{mm(BAND_W/2)}" y="-1" text-anchor="middle" font-family="sans-serif" font-size="2.5" fill="#666">'
            f'{band_name.upper()}</text>'
            f'{inner}'
            f'</g>'
        )

    # ── Row 2: Ruler strip (below bands, left side) ────────────────────────
    y_row2 = y_bands + BAND_H + 8   # y=216mm

    # Ruler strip: 16mm wide × 194mm tall
    ruler_inner = build_ruler_strip(RULER_W, BAND_H, RULER_SPACING, y_start=8.0)
    svg_parts.append(
        f'<g transform="translate({MARGIN_X},{mm(y_row2)})">'
        f'<text x="0" y="-1" font-family="sans-serif" font-size="2.8" fill="#666">'
        f'RULER  ·  40mm spacing  ·  {MARKER_DIAM_MM}mm marker</text>'
        f'{ruler_inner}'
        f'</g>'
    )

    # ── Body placement diagram (right of ruler, same row) ────────────────────
    body_x = MARGIN_X + BAND_W * 4 + 3 * 2 + 6   # right of band strips = 96mm
    body_y = y_row2
    body_w = A4_W - body_x - MARGIN_X             # 191mm
    body_h = BAND_H                               # 194mm
    body_svg = _build_body_placement_diagram(body_x, body_y, body_w, body_h)
    svg_parts.append(body_svg)

    # ── Row 3: Marker row + how-to instructions ─────────────────────────────
    y_marker = y_row2 + BAND_H + 6   # y=416mm — 4mm past page bottom (acceptable for notes)

    # Marker row
    marker_row = make_marker_row(MARKER_DIAM_MM, 12, strip_area_w,
                                  y_mm=4.0, label="cut: DSV markers")
    svg_parts.append(
        f'<g transform="translate({MARGIN_X},{mm(y_marker)})">'
        f'{marker_row}'
        f'</g>'
    )

    # How-to text below marker row
    howto = (
        f'<text x="{MARGIN_X}" y="{mm(y_marker + 14)}" '
        f'font-family="sans-serif" font-size="3.5" fill="#333" font-weight="bold">'
        f'HOW TO USE</text>'
        f'<text x="{MARGIN_X}" y="{mm(y_marker + 19)}" '
        f'font-family="sans-serif" font-size="2.8" fill="#555">'
        f'1. Cut each strip along its edges. </text>'
        f'<text x="{MARGIN_X}" y="{mm(y_marker + 24)}" '
        f'font-family="sans-serif" font-size="2.8" fill="#555">'
        f'2. Tape strip ends together. Wrap around body at marked level. </text>'
        f'<text x="{MARGIN_X}" y="{mm(y_marker + 29)}" '
        f'font-family="sans-serif" font-size="2.8" fill="#555">'
        f'3. Photograph front + side. Include ruler in frame. </text>'
        f'<text x="{MARGIN_X}" y="{mm(y_marker + 34)}" '
        f'font-family="sans-serif" font-size="2.8" fill="#555">'
        f'4. Apply marker dots to: shoulder points, neck base, hip points. '
        f'Use ruler strip to confirm scale.</text>'
    )
    svg_parts.append(howto)
    svg_parts.append("</svg>")

    full_svg = "\n".join(svg_parts)
    full_path = out_dir / "marker_sheet.svg"
    full_path.write_text(full_svg, encoding="utf-8")

    # ── Ruler strip only (1/3 A4 portrait) ─────────────────────────────────
    ruler_svg = "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{RULER_H:.1f}mm" height="{A4_H:.1f}mm" '
        f'viewBox="0 0 {RULER_H:.1f} {A4_H}">',
        f'<rect width="{RULER_H:.1f}" height="{A4_H}" fill="white"/>',
        f'<text x="3" y="5" font-family="sans-serif" font-size="3" fill="#555">'
        f'DSV Ruler  ·  40mm tick spacing  ·  verify ±0.2mm with calipers</text>',
        build_ruler_strip(RULER_W, A4_H, RULER_SPACING, y_start=8.0),
        "</svg>",
    ])
    ruler_path = out_dir / "ruler_strip.svg"
    ruler_path.write_text(ruler_svg, encoding="utf-8")

    # ── Cutting guide for adhesive sheet ────────────────────────────────────
    cut_svg = "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{A4_W}mm" height="{A4_H}mm" '
        f'viewBox="0 0 {A4_W} {A4_H}">',
        f'<rect width="{A4_W}" height="{A4_H}" fill="#fafafa" stroke="#999" stroke-width="0.5"/>',
        f'<text x="{MARGIN_X}" y="{MARGIN_Y + 4}" font-family="sans-serif" '
        f'font-size="4" fill="#555">DSV Cutting Guide — cut along lines, do not scale</text>',
    ])

    y_cur = MARGIN_Y + 8
    strip_info = [
        ("bust",       BAND_W,  BAND_SPACING,  BAND_H),
        ("underbust",  BAND_W,  BAND_SPACING,  BAND_H),
        ("waist",      BAND_W,  BAND_SPACING,  BAND_H),
        ("hip",        BAND_W,  BAND_SPACING,  BAND_H),
    ]
    for name, w, sp, h in strip_info:
        cut_svg += (
            f'<rect x="{MARGIN_X}" y="{mm(y_cur)}" width="{mm(w)}" height="{mm(h)}" '
            f'fill="none" stroke="#00aa00" stroke-width="0.4" stroke-dasharray="2,2" />'
            f'<text x="{mm(MARGIN_X + w + 1)}" y="{mm(y_cur + 3)}" '
            f'font-family="sans-serif" font-size="2.8" fill="#666">{name} {w}mm wide</text>'
        )
        y_cur += h

    cut_svg += "</svg>"
    cut_path = out_dir / "cutting_guide.svg"
    cut_path.write_text(cut_svg, encoding="utf-8")

    return {
        "full_sheet":  full_path,
        "ruler_strip": ruler_path,
        "cut_guide":   cut_path,
    }


# ── entry point ───────────────────────────────────────────────────────────────
def main():
    out_dir = pathlib.Path(__file__).parent.parent / "svg"
    files = build_marker_sheet(out_dir)
    for name, path in files.items():
        print(f"  ✓ {path} ({path.stat().st_size:,} bytes)")

    print(f"\nSheetSpec:")
    print(f"  marker_diam_mm = {MARKER_DIAM_MM}")
    print(f"  band_spacing_mm = {BAND_SPACING}")
    print(f"  ruler_spacing_mm = {RULER_SPACING}")
    print(f"  band_width_mm = {BAND_W}")
    print(f"  ruler_width_mm = {RULER_W}")


if __name__ == "__main__":
    main()