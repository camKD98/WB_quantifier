# WB_quantifier — method description, as implemented

Precise description of what the released code (`wb_quantifier_advanced.py` +
`quant_core.py`, v1.0.0) actually computes. Intended for checking thesis
methodology wording line-by-line. Option strings below are the exact values in
code; GUI labels are quoted.

## 1. Pipeline overview

per-lane rectangular ROI → 1-D intensity profile → baseline subtraction →
integration bounds → trapezoidal area (+ optional Gaussian model area) →
CSV/JSON export with provenance.

## 2. Lane ROI and profile extraction (`extract_profiles` / `qc.extract_profile`)

- Lane = axis-aligned rectangle `(x, y, w, h)` in image pixels; the first lane
  drawn fixes `lane_size` for subsequently auto-added lanes.
- The analysis array is the raw image as float64, reduced to 2-D
  (RGB→channel mean; multi-page→`image_page`). If the "Invert for analysis"
  checkbox (`invert_image_var`, default **off**) is set, the array is replaced
  by `max(arr) − arr`.
- Profile = **row-wise mean across the lane width**: `np.mean(roi, axis=1)`,
  length `h`, index = image row. (Not a sum, not a median.)

## 3. Peak detection (`detect_peaks` / `qc.detect_strongest_peak`)

- `scipy.signal.find_peaks` with `distance=20` px and adaptive prominence
  `max(0.05 × data_range, 1e-8)`.
- Polarity: if "Bands are bright" (`bands_are_bright`, default **off**) the
  profile is used directly; otherwise the negated profile is searched (dark
  bands become peaks).
- **Only the single most prominent peak per lane is retained** (max
  `prominences`; fallback max |height|). Automatic mode therefore quantifies
  at most one band per lane; interactive mode has no peak limit because the
  user marks bands.

## 4. Baseline subtraction (`calculate_baseline` / `qc.calculate_baseline`)

GUI radio options (`baseline_method`, default `"minimum"`):

| UI label | value | Behaviour |
|---|---|---|
| "Minimum" | `minimum` | flat line at `np.min(profile)` (per-lane) |
| "Background Boxes (Median)" | `background_boxes` | flat line at the **median of pooled pixels** from background-box ROIs associated with that lane (`background_lane_map`); falls back to the global median of all bg boxes, then to `np.min(profile)` |
| "Manual Region (Interactive)" | `manual_region` | interactive mode only: flat line at `np.median(profile[b_start:b_end])` of a user-dragged second region, stored per band; in non-interactive calls it silently remaps to `minimum` |

Additional code paths not reachable from the GUI:

- `linear`: exists but is commented out of the radio list. Fits a degree-1
  polynomial to the *n = max(3, len/10) highest-intensity* samples — i.e. it
  assumes background occupies the bright part of the profile (dark-band
  images, non-inverted). Its `bands_are_bright` branch is dead code (both
  branches select the same top-decile samples).
- `none`: accepted for backwards compatibility and remapped to `minimum`
  (not a zero baseline, despite the name).

Per-lane background boxes are produced only by the "BG from lanes" generator
(box drawn at a fixed offset below each lane); hand-drawn boxes contribute to
the global median only (`lane_map = None`).

## 5. Integration bounds (`integrate_peak` / `qc.integrate_peak`)

GUI radio options (`integration_method`, default `"fixed_width"`); operate on
`corrected = profile − baseline`:

| UI label | value | Bounds |
|---|---|---|
| "Fixed Width (Reference)" | `fixed_width` | `peak ± width//2` px, clamped; width = `reference_band_width` (user-set from a clean band, else auto-estimated from the first peak's 20%-height width) |
| "Peak % Height" | `percent_height` | walk left/right from the peak until `corrected ≤ threshold × peak_height`; threshold = GUI slider `peak_threshold` (0.05–0.5, default per control) |
| "Whole Lane (Box Total)" | `full_profile` | **mislabelled**: actually integrates the contiguous above-baseline region around the *dominant* corrected peak (walk to zero-crossings), not the whole lane box |
| "Interactive Selection" | `interactive` | user drags span per band (`start`, `end` stored verbatim) |

Any other method string → whole-profile `0..len`. `fixed_width` with
`width=None` falls through to that same whole-profile branch.

- Area = `np.trapz(corrected[start:end])` (trapezoid; `end` excluded per
  slicing). If the area is negative, area and height are sign-flipped.
- `height` = `corrected[peak_idx]`; `peak_idx` is the detected peak
  (automatic) or `argmin` of the selected region (interactive — note:
  **argmin assumes dark-band dips; for bright bands without inversion it
  picks the wrong extremum**, though the Gaussian path is polarity-aware).

## 6. Optional Gaussian reconstruction (interactive only)

Checkboxes (both default **off**, effectively mutually exclusive — "full"
wins if both end up set):

- "Use Gaussian fit (area only within selected region)" →
  `fit_method='single_gaussian'`, `fit_area_scope='selected_region'`
- "Use Gaussian fit and integrate full fitted curve" →
  `fit_method='single_gaussian_full_area'`, `fit_area_scope='full_gaussian'`

Implementation (`qc.fit_single_peak_gaussian`):

- Fit input = the **entire user-dragged region** of the corrected profile
  (`corrected[start:end]` vs `x = start..end−1`). There is no algorithmic
  selection of a "least-distorted segment" — the segment is whatever the user
  dragged; conservative dragging is the user's responsibility.
- `scipy.optimize.curve_fit` on `amp·exp(−(x−mu)²/2σ²)`, seeded at the region
  max; bounds: `amp ≥ 0`, `mu ∈ [x0−W, x1+W]`, `σ ∈ [0.5, max(2, 4W)]`
  (W = region width), `maxfev=5000`. Fit is polarity-aware (works on the
  positive excursion, remembers sign).
- Reported `area` **is the fitted model's area**, not raw integration:
  trapezoid of the fitted curve over the selected x-range, or the analytic
  `amp·σ·√(2π)` total area in "full" mode (which extrapolates beyond the
  bounds — i.e. estimates tails the user excluded).
- `height`/`peak_position` are likewise replaced by model values
  (peak = `round(mu)` clamped to the region).
- A failed fit (`<5` points, non-finite, or curve_fit exception) silently
  falls back to trapezoid and records `fit_method='none'` — a failed fit is
  indistinguishable from "fit never requested" in the record.

## 7. Export record

### CSV (`Export Data`)

Comment header then one header row, then one row per band. Comments:
`display_scale`, `tool=WB_quantifier`, `tool_version`, `git_commit`,
`export_utc`, `bands_are_bright`, `invert_for_analysis`, `peak_threshold`,
`image_page`, `image_sha256` (SHA-256 of the source TIFF — identifies the
exact input file without embedding a local path), plus LOQ-related lines
when background boxes exist.

Columns (order):

```
Source_File Lane Band
Area_corrected Area_display Area_raw
LOQ LOQ_model LOQ_empirical
BG_Mean BG_Median BG_SD
BG_Area_mean_empirical BG_Area_SD_empirical BG_Area_N_empirical
SNR_area_empirical
Height Width Peak_Position Start End
Baseline_Method Baseline_Value Baseline_Region_Start Baseline_Region_End
Integration_Method Fit_Method Fit_Area_Scope Fit_Area
Fit_Amp Fit_Mu Fit_Sigma Fit_Polarity
Lane_X Lane_Y Lane_W Lane_H
```

`Lane_X/Y/W/H` is the lane ROI in image pixels — combined with
`image_sha256`, band `Start`/`End`, and the method columns, a single CSV is
sufficient to re-derive every number from the raw TIFF.

Semantics:

- `Area_corrected` = baseline-subtracted trapezoid (or model area when a fit
  was used). `Area_raw` = trapezoid of the **uncorrected** stored profile
  over the same interval (recomputed at export from `self.lane_profiles` —
  see caveats).
- `Area_display = Area_corrected × display_scale`, where
  `display_scale = 1 / min(|Area_corrected|)` over nonzero values — a
  within-file normalization, not a physical unit.
- `Height`, `Width` (px), `Peak_Position`, `Start`, `End` = band geometry.
- LOQ columns: model `LOQ_area = 10·(σ_bg/√W_lane)·√H_band` and empirical
  (collapsed background-profile windows, `mean + 10·SD`); `LOQ` prefers
  empirical. `SNR_area_empirical = |Area_raw| / BG_Area_SD_empirical`.
- Provenance columns: baseline method + flat value + manual region bounds;
  integration method string; fit method/scope/area and Gaussian
  `(amp, mu, sigma)` + polarity. Older CSVs (pre-v1.0.0) do **not** contain
  these columns — see caveats.

### Lane configuration JSON (`Save Lane Configuration`)

`lanes`, `lane_size`, `reference_band_width`, `background_boxes`,
`background_lane_map`, `image_path`, `image_size`, `image_page`,
`display_params` (p_low/p_high/gamma), `tool_version`, `git_commit`,
`baseline_method`, `integration_method`, `bands_are_bright`,
`invert_for_analysis`, `peak_threshold`. Loading tolerates missing keys
(older configs load fine).

### LOQ text report (`Calc LOQ` → `Save Results`)

Version line, image name, background box/pixel counts, pooled μ/median/σ,
`LOD = med + 3.3σ`, `LOQ = med + 10σ` (intensity domain) and area-equivalent
LOQ. Display/export-image scaling (percentile clip + gamma) is purely visual
and never feeds quantification.

## 8. Known caveats / examiner questions (honest list)

1. **Provenance is forward-looking.** Baseline/fit/integration columns exist
   only in exports generated by v1.0.0+. CSVs exported for thesis analyses
   from older builds record geometry and areas but *not* the method fields —
   unless the corresponding lane-config JSON was saved alongside.
2. **Single band per lane** in automatic mode (strongest peak retained).
   Multi-band lanes require interactive mode.
3. **Interactive peak pick uses `argmin`** of the dragged region — correct
   for dark-band (non-inverted) profiles; for bright bands the pick can land
   on the wrong extremum (bounds and area are unaffected; only
   `Peak_Position`/`Height` misreport).
4. **`linear` baseline is hidden and unvalidated**; do not cite it.
5. **"Whole Lane (Box Total)" is a dominant-peak integration**, not a full
   box integral.
6. **Failed Gaussian fits degrade silently** to `fit_method='none'`.
7. **`full_gaussian` area extrapolates** beyond user bounds (amp·σ·√2π) —
   it is an estimate of total band content including excluded tails; the
   `selected_region` scope stays inside the bounds.
8. **`Area_raw` is recomputed at export** from in-memory profiles; if lanes
   were edited after analysis it may not match the analysed interval.
9. **"Finish" in interactive mode discards uncommitted results** — bands
   are stored to `band_data` only when paging past the last lane. (Known
   workflow quirk; results are safe if the user pages through all lanes.)
10. `np.trapz` is deprecated in NumPy ≥ 2.0 (still correct; pin is 1.26.4).
