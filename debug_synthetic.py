"""Debug: run each DSV component in isolation on synthetic images."""
import sys, pathlib, math
sys.path.insert(0, ".")
import cv2, numpy as np
from dsv import scale, detect, label

# Build the same front image as synthetic_test.py
width, height = 800, 1200
img = np.ones((height, width, 3), dtype=np.uint8) * 200
x_mid = width // 2
r = 24

SYNTHETIC_STRIP_PX = 80
strip_x = x_mid - SYNTHETIC_STRIP_PX // 2
strip_w = SYNTHETIC_STRIP_PX
TICK_SPACING_PX = 160

# Centre strip
cv2.rectangle(img, (strip_x, 50), (strip_x + strip_w, height - 50), (60, 60, 60), -1)
for tick_y in range(100, height - 50, TICK_SPACING_PX):
    cv2.line(img, (strip_x + strip_w // 2, tick_y - 6),
             (strip_x + strip_w // 2, tick_y + 6), (255, 255, 255), 6)

# Markers
markers_pos = [
    (80,  150), (x_mid-60, 150), (x_mid+60, 150), (720, 150),  # shoulder row
    (x_mid, 200),   # cf_neck
    (x_mid-120, 350), (x_mid+120, 350),  # bust
    (x_mid-115, 480), (x_mid+115, 480),  # underbust
    (x_mid, 600),   # cf_waist
    (x_mid-100, 600), (x_mid+100, 600),  # waist
    (x_mid-110, 750), (x_mid+110, 750),  # hip
    (x_mid, 480),   # cf_underbust
    (x_mid, 750),   # cf_hip
]
for cx_, cy_ in markers_pos:
    cv2.circle(img, (cx_, cy_), r, (0, 255, 0), -1)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ==== TEST 1: Scale detection ====
print("=== 1. Scale Detection ===")
strip_rect = scale.detect_scale_region(gray)
print(f"  strip_rect: {strip_rect}")

# Manual tick detection
x_range = (strip_x, strip_x + strip_w)
strip_slice = gray[:, x_range[0]:x_range[1]]
print(f"  strip slice shape: {strip_slice.shape}")
inv = cv2.bitwise_not(strip_slice)
_, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
proj = bw.sum(axis=0)
print(f"  projection shape: {proj.shape}, min={proj.min()}, max={proj.max()}")
kernel_size = max(3, strip_slice.shape[1] // 20)
print(f"  kernel_size: {kernel_size}")
kernel = np.ones(kernel_size, dtype=float) / kernel_size
smooth = np.convolve(proj.astype(float), kernel, mode='same')
threshold = smooth.max() * 0.3
print(f"  threshold: {threshold:.1f}")
peaks = []
for i in range(1, len(smooth) - 1):
    if smooth[i] >= smooth[i-1] and smooth[i] >= smooth[i+1] and smooth[i] > threshold:
        peaks.append(i + x_range[0])
print(f"  peaks (x positions): {peaks}")
print(f"  count: {len(peaks)}")

if len(peaks) >= 2:
    spacings = [peaks[i+1] - peaks[i] for i in range(len(peaks)-1)]
    print(f"  spacings: {spacings}")
    mm_per_px = 40.0 / float(np.median(spacings))
    print(f"  mm_per_px: {mm_per_px:.4f}")
else:
    print("  NOT ENOUGH PEAKS — would fail calibration")

# ==== TEST 2: Marker detection ====
print("\n=== 2. Marker Detection ===")
detected, colour = detect.detect_markers(img, "green")
print(f"  colour used: {colour}")
print(f"  markers found: {len(detected)}")
for m in detected[:5]:
    print(f"    cx={m['cx']}, cy={m['cy']}, r={m['r']:.1f}")

# ==== TEST 3: Labelling ====
print("\n=== 3. Labelling ===")
marker_diam_px = 48
mm_per_px = 0.25
fr = label.label_front(detected, x_mid, marker_diam_px, mm_per_px)
print(f"  front labels: {list(fr.labels.keys())}")
print(f"  flags: {fr.flags}")
print(f"  warnings: {fr.warnings}")

# ==== TEST 4: Full pipeline (fake) ====
print("\n=== 4. Pipeline Stage Order Check ===")
# The pipeline expects strip_rect, then calibrate
strip_rect2 = scale.detect_scale_region(gray)
if strip_rect2:
    sx, sy, sw, sh = strip_rect2
    print(f"  detected strip: x={sx}, w={sw}")
    ticks = scale.detect_ticks_on_strip(gray, (sx, sy, sw, sh), tick_spacing_px_hint=160)
    print(f"  ticks: {ticks}")
    if len(ticks) >= 2:
        mm_per_px2 = scale.calibrate_scale(ticks, 40.0)
        print(f"  mm_per_px: {mm_per_px2:.4f}")
    else:
        print(f"  FAIL: only {len(ticks)} tick(s)")
else:
    print("  FAIL: no strip region detected")