#!/usr/bin/env python3
"""Generate a deterministic synthetic Western-blot dataset for the quantifier.

Writes (relative to the repo root):
  example_data/synthetic_blot.tif        uint16 grayscale, ~1200x400
  example_data/synthetic_blot_lanes.json lane config in save_lane_config schema

Deterministic: numpy RNG seeded with a fixed constant; re-running produces
byte-identical output (modulo TIFF metadata-free encoding).
"""
import json
import os

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_PATH = os.path.join(HERE, "synthetic_blot.tif")
CFG_PATH = os.path.join(HERE, "synthetic_blot_lanes.json")

rng = np.random.default_rng(20240501)

# --- Canvas -----------------------------------------------------------------
H, W = 400, 1200                    # rows x cols (bands are horizontal streaks)
img = np.zeros((H, W), dtype=np.float64)

# Dark background (~800 counts) + gentle vertical/horizontal gradient + noise.
yy, xx = np.mgrid[0:H, 0:W]
img += 800.0
img += 0.4 * yy + 0.15 * xx                    # subtle illumination gradient
img += rng.normal(0.0, 18.0, (H, W))           # detector noise

# --- Lanes ------------------------------------------------------------------
# 8 evenly spaced vertical lane ROIs covering the band rows.
LANE_W, LANE_H = 80, 220
LANE_Y = 90                                    # top of lane ROI
MARGIN = 60
xs = np.linspace(MARGIN, W - MARGIN - LANE_W, 8).astype(int)
lanes = [[int(x), LANE_Y, LANE_W, LANE_H] for x in xs]

BAND_Y = 200                                   # nominal band centre row


def draw_band(cx, y, amp, sigma_y, sigma_x_edge=None, tail=None,
              second_peak=None):
    """Draw a horizontal streak: Gaussian in y, ~uniform in x with a soft
    (error-function) edge falloff across the lane width.

    amp      : peak counts above background
    sigma_y  : vertical Gaussian width (pixels)
    tail     : optional (amp, sigma, direction) exponential-ish tail added on
               one side in y to mimic smearing
    second_peak : optional (dy, amp, sigma_y) for a second band in the lane
    """
    x0, x1 = int(cx - LANE_W / 2) + 6, int(cx + LANE_W / 2) - 6
    sl_y = slice(max(0, y - 4 * int(sigma_y) - 60), min(H, y + 4 * int(sigma_y) + 60))
    yv = np.arange(sl_y.start, sl_y.stop, dtype=np.float64)

    prof = amp * np.exp(-0.5 * ((yv - y) / sigma_y) ** 2)
    if tail is not None:
        t_amp, t_sig, direction = tail
        # one-sided broad component: Gaussian centred above the main band
        dy = direction * 1.2 * t_sig
        prof += t_amp * np.exp(-0.5 * ((yv - (y + dy)) / t_sig) ** 2) * \
            np.where(direction * (yv - y) < 0, 1.0, np.exp(-(direction * (yv - y)) / (4 * t_sig)))
    if second_peak is not None:
        dy2, a2, s2 = second_peak
        prof += a2 * np.exp(-0.5 * ((yv - (y + dy2)) / s2) ** 2)

    xv = np.arange(x0, x1, dtype=np.float64)
    edge = 8.0                                 # px soft edge
    xw = 0.5 * (1 + np.tanh((xv - x0) / edge)) * 0.5 * (1 + np.tanh((x1 - xv) / edge))
    xw /= xw.max()
    img[sl_y, x0:x1] += np.outer(prof, xw)


cxs = xs + LANE_W // 2
# 5 clean Gaussian bands at ~same y, varying amplitude
for i, amp in enumerate([9000, 14000, 20000, 11000, 6000]):
    draw_band(cxs[i], BAND_Y + int(rng.integers(-3, 4)), amp, sigma_y=7.0)
# lane 5: faint band
draw_band(cxs[5], BAND_Y + 2, 1500, sigma_y=7.0)
# lane 6: smeared / tailed band (bright main band + upward smear)
draw_band(cxs[6], BAND_Y + 20, 16000, sigma_y=9.0,
          tail=(7000, 28.0, -1))
# lane 7: two bands (doublet)
draw_band(cxs[7], BAND_Y - 25, 9000, sigma_y=6.0,
          second_peak=(55, 7000, 6.5))

# Clip, quantise to uint16 and write.
img = np.clip(img, 0, 65535).astype(np.uint16)
tifffile.imwrite(IMG_PATH, img)

# --- Lane config (matches save_lane_config schema) --------------------------
config = {
    "lanes": lanes,
    "lane_size": [LANE_W, LANE_H],
    "reference_band_width": 40,
    "background_boxes": [
        [30, 20, 120, 50],
        [W - 150, 20, 120, 50],
    ],
    "background_lane_map": [None, None],
    "image_path": "example_data/synthetic_blot.tif",
    "image_size": [W, H],
    "image_page": 0,
    "baseline_method": "minimum",
    "integration_method": "percent_height",
    "bands_are_bright": True,          # synthetic bands are bright on dark bg
    "invert_for_analysis": False,
    "peak_threshold": 0.1,
    "display_params": {"p_low": 0.5, "p_high": 99.5, "gamma": 1.0},
}
with open(CFG_PATH, "w") as f:
    json.dump(config, f, indent=2)

print("Wrote", IMG_PATH, img.shape, img.dtype)
print("Wrote", CFG_PATH, "(%d lanes)" % len(lanes))
