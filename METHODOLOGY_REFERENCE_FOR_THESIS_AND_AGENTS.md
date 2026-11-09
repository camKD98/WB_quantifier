# Western Blot Quantifier (Advanced) — Methodology Reference

> **Status (v1.0.0, release-prep branch):** this document was originally written
> against a ~1971-line draft of the tool. It has been partially reconciled with
> the released code, but the **authoritative as-implemented reference is now
> `docs/METHOD_AS_IMPLEMENTED.md`** — consult that file for exact option names
> and behavior. Sections marked *(updated v1.0.0)* below were corrected;
> unmarked sections reflect the older draft and may be stale.

## 0) Purpose and scope
This document is a consolidated reference for:
1. Human-readable PhD thesis methodology writing, and
2. Efficient machine-agent context ingestion.

It includes only information visible in:
- Current conversation context (including prior conversation summary),
- Workspace files under `~/WB_quantifier`,
- User-provided CSV artifacts shown in attachments.

No gaps are filled by inference beyond what is directly available.

---

## 1) Source provenance (what this document is based on)

### 1.1 Code and docs inspected
- `wb_quantifier_advanced.py` (main implementation; ~2950 lines at v1.0.0; pure math now in `quant_core.py`)
- `image_utils.py`
- `README_ADVANCED.md`
- `FEATURES.md`
- `README.md`
- `requirements_advanced.txt`
- `requirements.txt`
- `example_config.json`
- `scripts/test_load.py`
- `scripts/inspect_tiff.py`

### 1.2 User-provided output artifacts inspected
- `data/example_blots/0002005_01/0002005_01_700.csv`
- `data/example_blots/0002008_01/0002008_01_Chemi.upper.csv`

### 1.3 Execution/validation evidence available in context
- `python3 -m py_compile ~/WB_quantifier/wb_quantifier_advanced.py` returned `OK`.
- GUI run command observed: `python wb_quantifier_advanced.py` with exit code 0 in context.

---

## 2) High-level project description (current state)
- The active analysis app is `wb_quantifier_advanced.py` (Tkinter + Matplotlib GUI).
- The GUI is tabbed (`ttk.Notebook`) with:
  - `Lane Selection` tab for quantification,
  - `Export Image` tab for non-destructive visual rendering and PNG export.
- Quantification is lane-profile based (ImageJ-style concept):
  - Each lane is a rectangular ROI,
  - Profile is row-wise mean over lane width,
  - Peaks are detected and integrated after baseline correction.

---

## 3) Conversation-derived development chronology (methodologically relevant)
This section captures changes explicitly described in conversation context and/or now present in code.

1. Export visualization separated from quantification by introducing an `Export Image` tab with live preview.
2. UI robustness improvements (layout, button visibility on macOS, instruction area scrollability, min window size).
3. Interactive selection bug fixed: `SpanSelector` is stored as `self.interactive_span_selector` to avoid garbage collection.
4. Interactive mode extended:
   - lane-to-lane persistence of selected bands,
   - optional per-band manual baseline-region workflow (two-step drag).
5. Baseline UI changed to disable linear option from the settings list (code path still exists internally).
6. Export controls refined:
   - Spinbox numeric entry paired with each slider,
   - slider `resolution=0.01` for fine control,
   - gamma minimum lowered to 0.1,
   - coarse trough-click step restored via `bigincrement`.
7. LOQ functionality added:
   - user draws one large or multiple small background boxes,
   - app computes background statistics and LOD/LOQ,
   - outputs include intensity-domain and area-equivalent LOQ,
   - save-to-text supported.

---

## 4) Detailed methodology implemented in code

## 4.1 Image loading and normalization
### Loader behavior (`image_utils.load_image`)
- TIFF-first strategy with `tifffile` (imported dynamically inside function).
- Fallback to Pillow when TIFF loading fails.
- Supports multi-page TIFF; returns metadata including:
  - `n_pages`, `page_shapes`, `dtype`, `min`, `max` (if available).
- Can return either:
  - displayable PIL image (default), or
  - raw numeric array (`return_raw=True`) for quantification.

### Non-destructive display scaling
- Percentile clipping (`p_low`, `p_high`) + gamma to produce display values.
- In `image_utils.normalize_to_uint8`, gamma is applied as `a ** gamma`.
- In Export tab preview/export pipeline, gamma is applied as `arr_norm ** (1/gamma)`.

**Important implementation note (for thesis transparency):**
- Two gamma conventions are present in code paths (`gamma` vs `1/gamma`) depending on function path.
- This is directly observable in code and should be explicitly acknowledged if display transformations are described.

## 4.2 Lane definition and profile extraction
- First lane drawn sets `lane_size`; subsequent lane additions in lane mode reuse this size.
- Coordinates are drawn on a scaled canvas and transformed back to image coordinates using `display_scale`.
- For each lane ROI (`x,y,w,h`):
  - Extract `gray_array[y:y+h, x:x+w]`,
  - Profile = mean across width (`axis=1`), i.e., 1D intensity vs vertical position.
- Optional inversion for analysis: `gray_array = max(gray_array) - gray_array` when enabled.

## 4.3 Peak detection
- Uses `scipy.signal.find_peaks`.
- Band polarity behavior:
  - If bands are bright: detect peaks on profile directly.
  - Else (default): detect on `-profile` so dark bands become peaks.
- Prominence set adaptively:
  - `prom = max(0.05 * data_range, 1e-8)`.
- Minimum distance default: 20 pixels.
- Current behavior keeps only the single strongest peak per lane (by prominence, fallback to magnitude).

## 4.4 Baseline correction *(updated v1.0.0)*
`calculate_baseline(profile, method)` implements:
- `minimum`: constant baseline at per-lane profile minimum.
- `background_boxes`: flat baseline at the **median of pooled background-box pixels** — per-lane value when lane-associated boxes exist (boxes created by "BG from lanes"), else global median, else profile minimum.
- `manual_region`: interactive mode only; per-band flat baseline at the median of a user-dragged region. Non-interactive calls remap it to `minimum`.
- `none`: remapped to `minimum` (backwards compatibility — it is *not* a zero baseline).
- `linear`: still implemented (degree-1 fit to the top-decile intensity samples) but commented out of the UI; its `bands_are_bright` branch is dead code.

**Current UI exposure in lane settings:**
- Exposed: `Minimum`, `Background Boxes (Median)`, `Manual Region (Interactive)`.

## 4.5 Peak integration *(updated v1.0.0)*
### Methods
- `fixed_width`:
  - width from manually set reference (`reference_band_width`) or auto-estimated from first peak.
  - integration limits centered around peak.
- `percent_height`:
  - left/right boundaries where corrected signal falls to threshold × peak height.
- `full_profile` (UI label "Whole Lane (Box Total)" — label is misleading):
  - integrates the contiguous above-baseline region around the *dominant* corrected peak, not the whole lane box.
- `interactive`:
  - manual span selection in dedicated window; optional per-band constrained
    single-peak Gaussian reconstruction (see §5a).

### Area and sign handling
- Corrected profile = profile − baseline.
- Area = trapezoidal integral over selected interval (`np.trapz`).
- If area negative, both area and height are sign-flipped to positive.

---

## 5) Interactive manual workflow (including per-band baseline regions)
- Interactive mode opens per-lane plotting UI.
- User can navigate lanes (`Previous`, `Next`), and selected bands are redrawn when revisiting a lane.
- Optional checkbox: `Use manual baseline region (per band)`.
- If manual baseline is enabled, selection is two-step per band:
  1. Drag band region,
  2. Drag flat baseline region.
- Baseline for that band becomes constant median of selected baseline region.
- Saved per-band metadata includes:
  - `baseline_source`,
  - `baseline_value`,
  - `baseline_region`.

## 5a) Optional constrained Gaussian reconstruction *(added v1.0.0)*
- Interactive mode only; two off-by-default checkboxes:
  - "Use Gaussian fit (area only within selected region)" → reported area = trapezoid of the fitted curve over the dragged interval.
  - "Use Gaussian fit and integrate full fitted curve" → reported area = analytic `amp·σ·√(2π)` (extrapolates beyond dragged bounds).
- Fit input: the whole user-dragged region of the baseline-corrected profile; there is **no algorithmic "least-distorted segment"** — the segment is whatever the user selected.
- `scipy.optimize.curve_fit`, single Gaussian, bounds `amp ≥ 0`, `mu ∈ [x0−W, x1+W]`, `σ ∈ [0.5, max(2,4W)]`.
- When a fit is used, reported `area`/`height`/`peak_position` are model values, not raw integration — an estimated reconstruction.
- Failed fits silently fall back to trapezoid with `fit_method='none'`.
- Per-band fit metadata (`fit_method`, `fit_params`, `fit_area_scope`) is serialized to CSV from v1.0.0 onward.

---

## 6) Background ROI and LOQ methodology (new functionality)

## 6.1 User interaction
- New draw mode toggle in Lane Selection tab:
  - `Lanes` mode,
  - `Background` mode.
- In `Background` mode, user can draw one or multiple background ROIs (cyan `BG1`, `BG2`, ...).
- Buttons:
  - `Clear BG` clears all background boxes,
  - `Calc LOQ` computes LOQ statistics.

## 6.2 Computation implemented
Given pooled pixels from all background boxes:
- $\mu = \text{mean background intensity}$
- $\sigma = \text{sample standard deviation}$ (`ddof=1`)
- $\text{LOD} = \mu + 3.3\sigma$
- $\text{LOQ} = \mu + 10\sigma$

### Area-equivalent LOQ (to match CSV `Area_raw` units)
Code implements:
- $\sigma_{profile} = \sigma / \sqrt{W}$, where $W$ = lane width in pixels,
- $\text{LOQ}_{area} = 10 \cdot \sigma_{profile} \cdot \sqrt{H}$,
- $H$ = `reference_band_width` if available, otherwise lane height.

The LOQ window displays:
- Number of BG boxes and pooled pixels,
- Mean and SD,
- Intensity-domain LOD and LOQ,
- `LOQ_area (raw)` and optionally `LOQ_area (display)`.

### Display-normalized LOQ area
If prior band data exist, display-scale uses the same normalization logic as CSV export:
- `display_scale = 1 / min_nonzero(abs(area_raw))`.
- `LOQ_area_display = LOQ_area_raw * display_scale`.

### Outputs
- On-screen dialog (`LOQ Calculator Results`).
- Save to text file via `Save Results` button.

---

## 7) Export Image tab methodology (visual-only pipeline)
- This tab is intentionally separated from quantification to avoid conflating display adjustment with quantitative processing.
- Controls:
  - Percentile Low: range 0–50, resolution 0.01, bigincrement 0.5, spinbox 0.01.
  - Percentile High: range 50–100, resolution 0.01, bigincrement 0.5, spinbox 0.01.
  - Gamma: range 0.1–3.0, resolution 0.01, bigincrement 0.1, spinbox 0.01.
  - Invert Colors checkbox.
- Export output: PNG from currently selected preview settings.

---

## 8) CSV export schema and scaling behavior

## 8.1 Header and columns *(updated v1.0.0)*
Exports include comment headers (`# display_scale=`, `# tool=`, `# tool_version=`,
`# git_commit=`, `# export_utc=`, `# bands_are_bright=`, `# invert_for_analysis=`,
`# peak_threshold=`, `# image_page=`, plus LOQ notes when background boxes exist).
Columns (21 original + 12 provenance columns appended in v1.0.0):
  - `Source_File`, `Lane`, `Band`
  - `Area_corrected`, `Area_display`, `Area_raw`
  - `LOQ`, `LOQ_model`, `LOQ_empirical`
  - `BG_Mean`, `BG_Median`, `BG_SD`
  - `BG_Area_mean_empirical`, `BG_Area_SD_empirical`, `BG_Area_N_empirical`
  - `SNR_area_empirical`
  - `Height`, `Width`, `Peak_Position`, `Start`, `End`
  - `Baseline_Method`, `Baseline_Value`, `Baseline_Region_Start`, `Baseline_Region_End`
  - `Integration_Method`, `Fit_Method`, `Fit_Area_Scope`, `Fit_Area`
  - `Fit_Amp`, `Fit_Mu`, `Fit_Sigma`, `Fit_Polarity`

(`Area_corrected` = baseline-subtracted integrated area, or the Gaussian model
area when a fit was used; `Area_raw` = trapezoid of the uncorrected stored
profile over the same interval.)

## 8.2 Scaling rule used for `Area_display` *(corrected v1.0.0 — was misdocumented)*
- Let nonzero absolute areas be $A_i = |Area\_corrected_i|$ — i.e. the scale is
  based on the *corrected* area (`band['area']`), **not** `Area_raw` as this
  document previously stated (the code's `raw_areas` variable name is misleading).
- If nonzero values exist: $display\_scale = 1 / \min_i(A_i)$; then
  $Area\_display = Area\_corrected \times display\_scale$.

So the smallest nonzero absolute corrected area is normalized to 1.0.

## 8.3 Observed examples from user-provided CSV artifacts
### Example A
File: `0002005_01_700.csv`
- Header: `# display_scale=2e+00`
- Values around `Area_raw ~ 0.63–0.98` map to `Area_display ~ 1.00–1.55`.

### Example B
File: `0002008_01_Chemi.upper.csv`
- Header: `# display_scale=5e+06`
- Example selected row includes `Area_display = 1110.105042`.
- This large display value is expected under the normalization rule when minimum nonzero `Area_raw` is very small.

---

## 9) Data structures and persisted artifacts

## 9.1 In-memory key structures
- `lanes`: list of `(x, y, w, h)`.
- `background_boxes`: list of `(x, y, w, h)`.
- `band_data`: list of dicts with at least lane/area/height/width/start/end/peak position; may also include baseline metadata in interactive workflow.

## 9.2 Lane configuration JSON (save/load) *(updated v1.0.0)*
Configuration includes (as implemented):
- `lanes`, `lane_size`, `reference_band_width`
- `background_boxes`, `background_lane_map`
- `image_path`, `image_size`, `image_page`
- `display_params` (`p_low`, `p_high`, `gamma`)
- `tool_version`, `git_commit` *(v1.0.0+)*
- `baseline_method`, `integration_method`, `bands_are_bright`,
  `invert_for_analysis`, `peak_threshold` *(v1.0.0+)*

A sample file exists as `example_config.json`.

---

## 10) Software environment and dependencies

## 10.1 Declared dependencies
From `requirements_advanced.txt`:
- `numpy>=1.24.0`
- `matplotlib>=3.7.0`
- `Pillow>=10.0.0`
- `scipy>=1.10.0`

From code behavior:
- `tifffile` is conditionally imported in `image_utils.load_image` (TIFF-first path), but not listed in `requirements_advanced.txt`.

## 10.2 Runtime/tooling context observed
- OS context supplied in conversation: macOS.
- Shell context supplied: zsh.
- Python 3.12 terminal context appears in session metadata.

---

## 11) Known implementation notes relevant to thesis reporting
1. Baseline linear option is still implemented but not selectable in current GUI baseline radio list.
2. Export/preview transformations are visual and separated from quantification intent.
3. Gamma exponent differs between utility normalization and export-tab pipeline (see Section 4.1).
4. Interactive baseline `manual_region` is per-band and only applied in interactive mode; non-interactive use remaps to minimum baseline.
5. One strongest peak per lane is currently retained by detection logic.

---

## 12) Items that should be included in a PhD methods chapter but are not available here
For each item below, exact values/details are unavailable in current context and should be provided from lab records or additional analyses.

1. Biological experimental design details (species/cell line, treatment groups, replicates, antibodies, loading controls).
2. Wet-lab protocol details (sample prep, gel %, transfer conditions, blocking/incubation/wash conditions, exposure settings).
3. Instrument calibration and acquisition parameters for each image (detector gain/exposure, bit depth, channel settings) beyond what can be inferred from TIFF metadata.
4. Validation against benchmark tools (e.g., ImageJ) with agreement metrics.
5. Statistical analysis plan for downstream inference (normalization strategy across blots, replicate aggregation, hypothesis tests, multiple testing correction).
6. Inter-operator and intra-operator reproducibility study design and results.
7. Quality-control exclusion criteria for lanes/bands/background boxes.
8. Error propagation and uncertainty model beyond LOQ formulas currently implemented.
9. Version locking / software release tag / commit hash corresponding to thesis analyses. *(resolved v1.0.0: `version.py` stamps `tool_version` + `git_commit` into every CSV export, lane-config JSON and LOQ report; a `v1.0.0` release tag is recommended — see `RELEASE_AUDIT_REPORT.md`.)*
10. Dataset manifest linking each reported figure/table to source image files and configuration files. *(partially addressed: `ARCHIVAL_MANIFEST.sha256` inventories all raw acquisitions with checksums; the figure→file mapping itself is still lab-record work.)*

Per user instruction wording, these are explicitly marked as:
- **"x should be included but is not available to me here"**.

---

## 13) Agent-ready compact context block
```yaml
project:
  name: Western Blot Quantifier (advanced GUI)
  main_file: wb_quantifier_advanced.py
  image_loader: image_utils.py
ui:
  tabs:
    - Lane Selection
    - Export Image
  lane_selection_controls:
    - Load Image
    - Clear Lanes
    - Add Lanes
    - Ref Band
    - Analyze
    - Draw mode: [Lanes, Background]
    - Clear BG
    - Calc LOQ
quant_methods:   # updated v1.0.0 — see docs/METHOD_AS_IMPLEMENTED.md
  profile_extraction: row-wise mean over lane width
  peak_detection:
    function: scipy.signal.find_peaks
    min_distance_px: 20
    prominence: max(0.05*range, 1e-8)
    retained_peaks_per_lane: strongest_only   # automatic mode; interactive mode is user-bounded
  integration:
    modes: [fixed_width, percent_height, full_profile, interactive]
    note: full_profile = dominant-peak above-baseline region (UI label "Whole Lane (Box Total)" is misleading)
    interactive_fit: optional constrained single-peak Gaussian (selected-region or full-curve area)
  baseline:
    gui_exposed: [minimum, background_boxes, manual_region]
    implemented_but_hidden: [linear]
    remapped_to_minimum: [none, manual_region(non-interactive)]
loq:
  background_input: one_or_more_background_boxes
  equations:
    mu: mean(background_pixels)
    sigma: std(background_pixels, ddof=1)
    lod_intensity: mu + 3.3*sigma
    loq_intensity: mu + 10*sigma
    loq_area_raw: 10*(sigma/sqrt(W))*sqrt(H)
  W: lane_width_px
  H: reference_band_width_or_lane_height
csv_export:   # updated v1.0.0 — 33 columns; see docs/METHOD_AS_IMPLEMENTED.md §7
  header_comments: [display_scale, tool, tool_version, git_commit, export_utc,
                    bands_are_bright, invert_for_analysis, peak_threshold, image_page]
  columns:
    - Source_File
    - Lane
    - Band
    - Area_corrected
    - Area_display
    - Area_raw
    - LOQ
    - LOQ_model
    - LOQ_empirical
    - BG_Mean
    - BG_Median
    - BG_SD
    - BG_Area_mean_empirical
    - BG_Area_SD_empirical
    - BG_Area_N_empirical
    - SNR_area_empirical
    - Height
    - Width
    - Peak_Position
    - Start
    - End
    - Baseline_Method
    - Baseline_Value
    - Baseline_Region_Start
    - Baseline_Region_End
    - Integration_Method
    - Fit_Method
    - Fit_Area_Scope
    - Fit_Area
    - Fit_Amp
    - Fit_Mu
    - Fit_Sigma
    - Fit_Polarity
  display_scale_rule: 1/min_nonzero_abs(Area_corrected)   # corrected basis, NOT Area_raw
  area_display_rule: Area_corrected * display_scale
observed_outputs:
  file_1:
    name: 0002005_01_700.csv
    display_scale: 2e+00
  file_2:
    name: 0002008_01_Chemi.upper.csv
    display_scale: 5e+06
    selected_area_display_example: 1110.105042
dependencies:
  requirements_advanced:
    - numpy>=1.24.0
    - matplotlib>=3.7.0
    - Pillow>=10.0.0
    - scipy>=1.10.0
  conditionally_used:
    - tifffile
missing_for_thesis:
  - experimental_biology_details
  - wet_lab_protocol_details
  - acquisition_parameter_table
  - validation_against_external_tool
  - statistical_inference_plan
  - reproducibility_studies
  - QC_exclusion_criteria
  - uncertainty_model_beyond_current_loq
  - analysis_commit_hash_or_release_tag
  - dataset_manifest_figure_to_file_mapping
```

---

## 14) Suggested citation text template *(updated v1.0.0 — verify against docs/METHOD_AS_IMPLEMENTED.md)*
"Western blot lane quantification was performed using WB_quantifier v1.0.0, a custom Python GUI (`wb_quantifier_advanced.py`; quantification routines in `quant_core.py`), with lane-wise profile extraction (row-wise mean intensity over each lane ROI), strongest-peak detection (`scipy.signal.find_peaks`), per-lane baseline correction (profile minimum, background-box median, or manually selected flat region), and trapezoidal integration over automatic or user-defined bounds. For smeared bands, an optional constrained single-peak Gaussian reconstruction over the user-selected region could report model-based areas (used only as an estimate, never by default). Each export records tool version, git commit, integration bounds, baseline method/value, and Gaussian fit parameters alongside raw and corrected areas. Exported values included raw integrated area (`Area_raw`), baseline-corrected area (`Area_corrected`), and normalized display area (`Area_display`), where display scaling was defined per file as the inverse of the minimum nonzero absolute `Area_corrected`. For limit-of-detection/quantification estimation, one or more background ROIs were manually selected; pooled background pixels were used to compute $\mu$ and $\sigma$, with $LOD=\mu+3.3\sigma$ and $LOQ=\mu+10\sigma$."

(If additional protocol details are required, they are not available in the current context and must be added from laboratory records.)
