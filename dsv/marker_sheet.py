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
BAND_H = A4_H - 2 * MARGIN_Y

# Ruler strip — 1/3 A4 portrait width
RULER_H = A4_W / 3   # ≈ 99mm


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
                f'fill="#333">cut: {label}</text>')

    return "".join(circles) + label_el


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
    # 4 band strips stacked, then ruler strip + marker guide
    strip_area_w = A4_W - 2 * MARGIN_X
    n_bands = 4
    band_cell_h = (A4_H - 2 * MARGIN_Y) / (n_bands + 0.5)   # 0.5 for ruler
    ruler_cell_h = band_cell_h * 0.5

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{A4_W}mm" height="{A4_H}mm" '
        f'viewBox="0 0 {A4_W} {A4_H}">',
        # Background
        f'<rect width="{A4_W}" height="{A4_H}" fill="white"/>',
        # Title + meta
        f'<text x="{MARGIN_X}" y="{MARGIN_Y + 4}" font-family="sans-serif" '
        f'font-size="4" fill="#555">DSV Marker Sheet v1.0 — print at 100% (no fit)</text>',
        f'<text x="{A4_W - MARGIN_X}" y="{MARGIN_Y + 4}" text-anchor="end" '
        f'font-family="sans-serif" font-size="3" fill="#aaa">'
        f'check with calipers: bands 25mm ±0.2, ruler 40mm ±0.2</text>',
    ]

    y_cursor = MARGIN_Y + 6

    # Band strips
    band_strips = ["bust", "underbust", "waist", "hip"]
    for band_name in band_strips:
        inner = build_band_strip(BAND_W, band_cell_h, BAND_SPACING, y_start=5.0)
        svg_parts.append(
            f'<g transform="translate({MARGIN_X},{mm(y_cursor)})">'
            f'<text x="0" y="-1" font-family="sans-serif" font-size="2.8" fill="#666">'
            f'{band_name.upper()}  ·  25mm spacing</text>'
            f'{inner}'
            f'</g>'
        )
        y_cursor += band_cell_h

    # Ruler strip + marker guide row
    ruler_inner = build_ruler_strip(RULER_W, ruler_cell_h, RULER_SPACING, y_start=5.0)
    marker_row  = make_marker_row(MARKER_DIAM_MM, 12, strip_area_w,
                                  y_mm=ruler_cell_h / 2, label="DSV markers")

    svg_parts.append(
        f'<g transform="translate({MARGIN_X},{mm(y_cursor)})">'
        f'<text x="0" y="-1" font-family="sans-serif" font-size="2.8" fill="#666">'
        f'RULER  ·  40mm spacing  ·  markers: {MARKER_DIAM_MM}mm dia</text>'
        f'{ruler_inner}'
        f'{marker_row}'
        f'</g>'
    )

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