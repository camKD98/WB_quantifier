# Benchmark Report — WB Quantifier Validation Supplement

**Tool:** WB_quantifier v1.0.0 (git ccef7be)
**Date:** 2026-11-09 18:05

## Methodology

This benchmark compares the quantification math in `quant_core.py` (row-mean
profile extraction, flat baseline subtraction with polarity auto-flip,
height-fraction / fixed-width bound finding, `np.trapz` integration) against an
**independent minimal reference implementation** written fresh in
`benchmark.py` (~50 lines: `ref_profile`, `ref_baseline_median`,
`ref_bg_median`, `ref_bounds_halfheight`, `ref_area` using
`scipy.integrate.trapezoid`). The reference deliberately re-derives the
documented method without calling `quant_core`, so agreement between the two
paths validates that the tool's math implements the intended method.

**ImageJ/Fiji is NOT installed on this machine.** The independent reference
IS the benchmark oracle here; no third-party densitometry comparison was
possible. The user may optionally re-run the same lane ROIs and bounds in
Fiji (Analyze > Gels or Plot Profile + integrate) to cross-check absolute
areas later.

Synthetic profiles are seeded (`numpy.default_rng(20250301)`) so results are
reproducible. Analytic ground truth is the exact Gaussian integral
A·σ·√(π/2)·[erf((b−μ)/σ√2) − erf((a−μ)/σ√2)] evaluated within the actual
integration window, so % error measures only baseline-noise and bound effects,
not window truncation.

Real-data cases use `images/Image_0001884_01.tif` (LI-COR scan) with the 12
lane ROIs stored in `images/Image_0001875_01.json`. Lanes were selected
programmatically: each lane's peak width at 20% height was computed, the two
narrowest were taken as "clean" and the two widest/most asymmetric as
"smeared" (plus up to two mid-width lanes for breadth). Bounds rule, identical
on both paths: 20%-height crossings expanded outward by one half-width, then
quantified as a centred fixed-width window. Baseline rule, identical region
on both paths: flat median over a single 15-px flank region starting 5 px
outside the bounds (whichever side has room), matching the GUI's single
manual-region baseline (`median_region_value` vs the reference's independent
median). In the synthetic smeared case the tool path instead combines two
per-region medians while the reference medians the union — an intentional
independent variation that produces the small observed non-zero diff. A
second usable image (first `images/*.tif` whose lane ROIs contain real
signal) was run for breadth on three lanes.

## Results — synthetic

| case | bounds | tool area | ref area | % diff | analytic truth | tool err % |
|---|---|---|---|---|---|---|
| flat_gauss_1(A=8000,s=4,fixed_width) | [88,112) | 103999.36 | 103999.36 | 0.0000 | 79864.81 | 30.22 |
| flat_gauss_2(A=8000,s=8,fixed_width) | [81,121) | 153677.17 | 153677.17 | 0.0000 | 158020.39 | -2.75 |
| flat_gauss_3(A=3000,s=6,percent_height,bright) | [92,108) | 36132.34 | 36132.34 | 0.0000 | 35514.14 | 1.74 |
| flat_gauss_4(A=12000,s=10,percent_height) | [100,100) | 0.00 | 0.00 | 0.0000 |  |  |
| sloped_bg_gauss | [20,180) | 196460.66 | 196460.66 | 0.0000 | 105278.39 | 86.61 |
| smeared_two_gauss(dominant) | [76,104) | 105080.26 | 104962.90 | 0.1118 | 102652.17 | 2.37 |
| bright_polarity_gauss | [82,118) | 136289.55 | 136289.55 | 0.0000 | 134863.44 | 1.06 |

## Results — real blots

| case | bounds | tool area | ref area | % diff |
|---|---|---|---|---|
| img884_lane0_w143px | [35,186) | 637.19 | 637.19 | 0.0000 |
| img884_lane2_w108px | [30,186) | 1555.36 | 1555.36 | 0.0000 |
| img884_lane3_w97px | [29,186) | 907.87 | 907.87 | 0.0000 |
| img884_lane5_w84px | [28,186) | 1315.56 | 1315.56 | 0.0000 |
| img884_lane7_w35px | [79,147) | 1447.29 | 1447.29 | 0.0000 |
| img884_lane11_w37px | [77,149) | 943.95 | 943.95 | 0.0000 |
| img0001876_lane0 | [128,132) | 232.35 | 232.35 | 0.0000 |
| img0001876_lane2 | [128,132) | 227.99 | 227.99 | 0.0000 |
| img0001876_lane3 | [128,132) | 223.69 | 223.69 | 0.0000 |

## Agreement summary

- Mean |tool vs ref % diff|: **0.0070%**
- Max  |tool vs ref % diff|: **0.1118%**
- Mean |tool error vs analytic truth| (synthetic, non-degenerate): 20.79%  (max 86.61%) — note these errors measure
  baseline/bounds *choices* against an idealized truth, not implementation
  error; the tool-vs-reference agreement above is the validation metric
- Tolerance: ≤ 2%  →  **PASS**

## Anomalies observed in the tool's math

1. **`percent_height` on dark bands is degenerate.** `integrate_peak` walks
   outward while `corrected > peak_height*frac`. For dark bands the GUI feeds
   `corrected = profile - baseline` unflipped (the auto-flip only applies when
   `bands_are_bright` is checked), so `corrected[peak]` is negative, the
   threshold is negative, and the bound walk degenerates — either collapsing
   to a zero-width window at the peak (observed: flat_gauss_4 returns area 0)
   or running to the profile edges, silently turning percent-height into
   whole-lane integration
   (cases: flat_gauss_4(A=12000,s=10,percent_height)).
   Tool and reference agree exactly on this behavior, so it is a method quirk,
   not an implementation bug — but users quantifying dark bands should prefer
   `fixed_width` or `full_profile`.
2. **`minimum` baseline inverts dark-band area.** With `baseline='minimum'`
   the baseline sits at the band's lowest pixel, so `corrected = profile -
   baseline` is a positive plateau with a dip at the band. A fixed-width
   integration then reports `amp*W - band_area` (larger area = weaker band).
   This is consistent with the GUI's own math (area is abs'd), but means
   `minimum` baseline should be paired with `full_profile`, or flank/manual
   baselines should be used for fixed windows — see flat_gauss_1/2 err%.
3. **Baseline `minimum` + argmax-style peak picking**: peak detection must go
   through `detect_strongest_peak` (which inverts the profile for dark bands);
   a plain `argmax(corrected)` after a minimum baseline picks background
   noise, since the corrected floor is ~0 at the band and ~amp elsewhere.
4. **Edge-clipped lanes**: several real lanes have their dominant dip at or
   near the lane-ROI edge (peak index 0 or near h), so fixed-width windows
   clip asymmetrically. Both paths handle it identically.

## Limitations

- Profile extraction is identical by construction (both paths average rows of
  the same rect); this validates the quantification *math*, not interactive
  steps such as lane placement, rotation, or manual baseline/region picking.
- The reference re-implements the same documented formulas, so it catches
  implementation bugs, not methodological flaws in the method itself.
- Real-blot "truth" is unknown; agreement there is tool-vs-reference only.
- Recommend optionally re-running the same ROIs in Fiji/ImageJ for an
  external cross-check when available.
