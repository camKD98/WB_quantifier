# WB_quantifier — Release Audit Report

**Date:** 2026-11-09 · **Prepared on branch:** `release-prep` · **Tool version stamped:** `WB_quantifier v1.0.0`
**Scope:** public-readiness, audit-caveat disposition, code↔thesis consistency check, artifacts for thesis citation.

> Nothing has been pushed, deleted from disk, or made public. All raw data is still
> on disk; every removed file remains reachable in git history. The release-prep
> branch contains 5 new commits on top of `45ec271` (master HEAD).

---

## 1. Public-readiness findings

### 1.1 Sensitive material found and handled

| Item | Severity | Status |
|---|---|---|
| `.specstory/` AI session logs | **High** — ~1,100 `/Users/cambrinkd/…` paths + shell prompt `cambrinkd@admins-MacBook-Air` embedded in exported session transcripts; **already present in *pushed* history** (file `2025-12-22_20-29Z-…md` is in `origin/master` tree) | Untracked from release branch; **must also be removed from history** (see §1.4) — file deletion alone leaves the blobs on GitHub's servers |
| Commit author identity `camKD98 <k20112660@kcl.ac.uk>` on all 14 commits | Medium — KCL student k-number email on every commit, incl. pushed ones | Handled by the fresh-history plan (§1.4): the public repo's commits will carry `camKD98` + GitHub noreply. Decide whether to also rewrite/replace the private repo |
| `/Users/cambrinkd/…` paths in docs | Low | **Scrubbed**: `BUILD_INSTRUCTIONS.md` (×2), `WINDOWS_BUILD.md` (×2), `METHODOLOGY_REFERENCE…md` (×4, incl. two `Downloads/cambrinactinup…` paths → `data/example_blots/…`) |
| `C:\Users\PFP_licor\Cambrin\Images\` in `raw_image_studio/**/0001703_01_shape.txt`, `0001704_02_shape.txt` | Low (first name "Cambrin" in instrument-PC path) | Leaves the repo with `raw_image_studio/`; still present on disk — scrub if the data archive itself is ever published |
| `images/Image_0001875_01.json` → `"image_path": "/Users/cambrinkd/…"` | Low | Untracked with `images/`; note: **any saved lane-config JSON records absolute `image_path`** — check before sharing configs |
| `.DS_Store`, `__pycache__/`, `.vscode/`, AppleDouble `._*` files | Junk | Untracked + gitignored |
| ~20 `wb_quantifier_backup copy*.py` files | Clutter | Removed from working tree (all preserved in commit `45ec271`; every backup's methods verified to be a strict subset of the current file — nothing unique was lost) |
| `METHODOLOGY_REFERENCE_FOR_THRSIS_AND_AGENTS.md` | Typo'd byte-identical duplicate | Removed |

**No credentials, tokens, or API keys found** anywhere (tree or history). `*_acq.txt` instrument files contain model/serial (`Odyssey Fc`, `OFC-0505`) and experiment labels (HUVEC/FAK/EC/VEGF conditions) but all operator/identity fields are empty. **Not verified** (needs `exiftool`/`tiffinfo`, unavailable): TIFF tag metadata inside the binary images — recommended before publishing any raw file.

### 1.2 `raw_image_studio/` + `images/` plan (~460 MB, ~250 files)

- Both dirs are **untracked on `release-prep`** (`git rm --cached`) and stay on disk untouched. They were committed in the *initial* commit `50bd51c`, so they still occupy ~500 MB of git history.
- `ARCHIVAL_MANIFEST.sha256` (241 files, verified) fingerprints every raw file — keep it with the archive copy.
- **Uniqueness:** `raw_image_studio/` holds the only copies in this workspace of ~59 LI-COR acquisitions (`22_12_25_wb_t-fak recover/`, `allwbresultsup224thoct/`). `images/` overlaps partially (e.g. `0001883/0001884` appear in both under different names — same acquisitions, different exports). **I cannot verify copies exist elsewhere** — treat `raw_image_studio/` as unique until confirmed.
- **Recommended archival steps (yours to run):**
  1. Copy `raw_image_studio/` + `images/` to institutional storage / a data repo (Zenodo or KCL's RDM service).
  2. Verify with `shasum -a 256 -c ARCHIVAL_MANIFEST.sha256` in the copy destination.
  3. Only then consider the git-history rewrite in §1.4.
- These are real unpublished experiment blots (HUVEC pFAK/tFAK/actin) — do **not** ship them inside the public code repo; archive as a citable dataset instead (Zenodo DOI can be cited alongside the software).

### 1.3 Repo hygiene now in place

`.gitignore` (pycache/DS_Store/specstory/vscode/build/data dirs), `LICENSE` (MIT), rewritten `README.md`, `CITATION.cff` (**placeholder author name — replace with your real name/ORCID before release**), pinned `requirements.txt` (numpy 1.26.4, matplotlib 3.10.0, Pillow 11.1.0, scipy 1.15.1, tifffile 2025.12.20 — the conda env that generated the current code) + `requirements-dev.txt` (pytest), CI updated to install requirements + run tests before PyInstaller. `example_data/` ships a deterministic synthetic blot + lane config so users can try the GUI without real data.

### 1.4 Recommended release sequence (fresh history, zero risk)

Current pushed history contains the session logs, the 500 MB of TIFFs, and the KCL email — all already on the private remote. Simplest safe path:

```bash
# 1. Archive raw data off-repo first (§1.2). Then, in a scratch clone or this repo:
git checkout --orphan public-release release-prep   # same tree, no parents
git -c user.name="camKD98" \
    -c user.email="camKD98@users.noreply.github.com" \
    commit -m "WB_quantifier v1.0.0"
git tag -a v1.0.0 -m "WB_quantifier v1.0.0"
# 2. Create a NEW public GitHub repo (e.g. keep this one private as archive):
#    github.com/camKD98/WB_quantifier-public (or rename the old repo and reuse the name)
git remote add public git@github.com:camKD98/<new-repo>.git
git push public public-release:master --tags
# 3. The existing camKD98/WB_quantifier stays PRIVATE as the full-history archive.
```

Cite **v1.0.0 on the public repo** (commit hash = whatever the orphan commit lands as — fill it in after step 1; `version.py` will also stamp it into future exports automatically). This loses no history: `master`/`release-prep` here keep all 19 commits locally forever.

---

## 2. Audit-caveat disposition

| Prior audit caveat | Disposition |
|---|---|
| "Method artifact, single smoke test, no test suite" | **Fixed.** `tests/` — **44 pytest cases, all passing** (~9 s): synthetic ground truth for every `quant_core` function (profile extraction, all four baseline modes + remaps, all three integration bound-walks + edge cases, Gaussian fit recovery/polarity/failure, band-width estimate), GUI-adapter equivalence (`app.method ≡ qc.function`), CSV export schema incl. provenance columns, headless import + real-Tk smoke. |
| "No ImageJ benchmark" | **Answered with the fallback.** No ImageJ/Fiji is installed on this machine (checked `/Applications`). `validation/` implements an independent ~50-line scipy reference and compares on 16 synthetic + real-lane cases: **mean \|diff\| = 0.007%, max = 0.11% → PASS ≤2%** (`validation/BENCHMARK_REPORT.md`, `results.csv`). An optional Fiji re-run is documented there. The benchmark also surfaced genuine method quirks — see §3.3. |
| "Outputs don't record version" | **Fixed.** `version.py` (`__version__='1.0.0'`, `get_git_commit()`) stamps `# tool_version`, `# git_commit`, `# export_utc` into every CSV, and `tool_version`/`git_commit` into lane-config JSONs + LOQ reports. Note: historical CSVs still lack it — see §3.2. |
| "`METHODOLOGY_REFERENCE.md` admits gaps / stale" | **Fixed.** Doc corrected in place (baseline list, integration list, 33-column schema, `display_scale` basis, JSON keys, Gaussian section, version-lock item) with a pointer to the new authoritative `docs/METHOD_AS_IMPLEMENTED.md`. |
| No tags/releases | **Prepared.** `v1.0.0` tag recommended in §1.4; CI already builds executables on `v*` tags. |

---

## 3. Code behavior vs thesis appendix — discrepancies (verbatim claims checked)

Appendix claims were checked against the code directly. **Supported:** lane ROI → row-mean profile; background-box **median** baselines (per-lane → global → min fallback); manual flat baseline = median of a dragged region; trapezoid integration; optional constrained single-Gaussian (bounds `amp≥0, mu∈region±W, σ∈[0.5,4W]`, off by default); conservative user-defined bounds.

### 3.1 Discrepancies that need thesis wording care

1. **"Gaussian reconstruction using the least-distorted segment"** — *no such segment selection exists.* The fit input is the **entire user-dragged region** (`corrected[start:end]`); nothing algorithmically picks a least-distorted sub-segment. The claim holds only if "the user conservatively drags the cleanest part" — recommend wording: *"over a conservatively user-selected region"* rather than "least-distorted segment".
2. **"Export/audit trail: baseline method+regions, integration method, fit method+parameters"** — these were **computed but never serialized** before this work: `band_info` carried `baseline_source/baseline_region/fit_method/fit_params` yet `export_data` ignored them. From v1.0.0 the CSV carries `Baseline_Method/Value/Region_*`, `Integration_Method`, `Fit_Method/Area_Scope/Area/Amp/Mu/Sigma/Polarity`, `Lane_X/Y/W/H` and an `# image_sha256` line — so the claim is now true **for exports generated after this release**, not for historical thesis CSVs. If the thesis claims the existing outputs contain this record, that needs care — see §5.
3. **"Case B: lane/region-local baseline, not global"** — supported but only as **flat** local baselines (per-lane bg-box median, or per-band manual median). No sloped/spatially-varying baseline is reachable from the GUI (`linear` exists but is disabled and buggy — dead duplicated polarity branch).
4. **"Integration method" wording**: the UI's "Whole Lane (Box Total)" (`full_profile`) is **not** a box total — it integrates the contiguous above-baseline region around the dominant peak. If the appendix implies whole-box integration anywhere, that's not what the code does.
5. **Peak counting**: automatic mode keeps **only the single most prominent peak per lane**. If any prose implies multi-band-per-lane automatic detection, it's interactive-mode only.
6. `detect_peaks` polarity uses the `bands_are_bright` checkbox; the interactive **peak pick is `argmin` of the dragged region** — fine for dark-band dips but polarity-blind (a bright-band interactive analysis can mark `Peak_Position`/`Height` at the wrong extremum; bounds/areas unaffected).
7. Minor: a failed Gaussian fit **silently records `fit_method='none'`** — indistinguishable from "never requested". The "Full Gaussian" area mode (`amp·σ·√2π`) **extrapolates beyond the dragged bounds** — it's a total-band estimate, not a within-bounds measurement.

### 3.2 Provenance completeness check (job 3a)

Now exported per band: bounds, baseline method + flat value + manual region, integration method, fit method/scope/params/polarity, raw + corrected area, lane ROI, image page + source SHA-256, tool version, git commit, polarity/invert flags, display scale. A v1.0.0 CSV is self-contained for re-analysis from the raw TIFF. **Caveat:** exports made before this release lack everything after `End` — the thesis's audit-trail claim applies to v1.0.0+ outputs.

### 3.3 Validation-surfaced method quirks (real, documented in `validation/BENCHMARK_REPORT.md`)

- **`percent_height` degenerates on non-inverted dark bands**: `corrected[peak] ≤ 0` → threshold ≤ 0 → bounds collapse to zero width (area ≈ 0). Valid only for positive-peak profiles (inverted analysis or bright bands).
- **`minimum` baseline on non-inverted dark bands** puts the baseline at the dip floor → the integrated "area" measures the background plateau (≈ `amp·W − band`), not the band. Valid only for positive-peak profiles. (Historical CSVs show negative `Height` values → those runs used bg-level baselines, consistent with `background_boxes`/`manual_region`, not `minimum` — but **you should confirm which baseline/method settings were actually used for each thesis export**, since they weren't recorded.)
- Peak detection assumes the internal polarity flip (dark bands detected via `-profile`); `argmax(corrected)` after a `minimum` baseline would lock onto background.

**Post-audit verification against a real thesis CSV** (`DEC_PFAK_1_LEFT_2_RIGHT_minus_background_noise_fitting.csv`, source `0001875_01_Chemi_20251119.TIF`, float16 reflectance): every numeric column is self-consistent with the audited pipeline — `SNR_area_empirical = Area_raw/BG_Area_SD_empirical` checks to <0.1%, `Height` equals the corrected peak in raw reflectance units (e.g. 3.2e-4), and the implied baseline (~3–6e-4, lane-local) sits far above the global bg-box level (~2.3e-6), confirming the manual-region baseline path. An earlier concern that `Height` values were ~1e6× profile scale was a column-misalignment on my part (612.5 is `SNR`, not `Height`); no discrepancy remains. Historical method provenance is preserved by the filename convention (`{integration}_{noise-variant}_{fitting|no_fitting}`) + per-image lane/background JSON sidecars — adequate for re-analysis, though less explicit than the v1.0.0 column record. The copy of `wb_quantifier_advanced.py` in the separate `RAW_WB_IMAGES` data workspace is byte-identical (MD5 `775f7081…`) to this repo's file — there is no divergent export implementation.

---

## 4. Artifacts produced for the thesis

| Artifact | Path |
|---|---|
| Worked-example figure (real data: clean lane 7; smeared lane 3; lane 3 Gaussian reconstruction, amp 34.4/μ 116.2/σ 11.3, selected 740 vs full 977 vs bounded 738 a.u.) | `docs/figures/worked_example.{pdf,png}` + `worked_example_caption.txt` + `_contact_sheet.png` (honest lane-choice provenance) |
| As-implemented method description (exact option strings, examiner-level caveats) | `docs/METHOD_AS_IMPLEMENTED.md` |
| Independent benchmark supplement | `validation/BENCHMARK_REPORT.md` + `benchmark.py` + `results.csv` |
| Test suite | `tests/` (44 tests) |
| Version/citation string | `version.py`; `get_version_string()` → `WB_quantifier v1.0.0 (git <sha>)`; `CITATION.cff` (name placeholder) |
| Updated methodology reference | `METHODOLOGY_REFERENCE_FOR_THESIS_AND_AGENTS.md` (reconciled) |
| Data-integrity manifest | `ARCHIVAL_MANIFEST.sha256` (241 files) |
| Synthetic example dataset | `example_data/` (regenerable via `generate_synthetic_blot.py`) |
| Release branch | `release-prep` — 5 commits: backups removed → data untracked → core extraction+provenance → hygiene → tests/benchmark/figure/docs |

---

## 5. Suggested thesis additions

**Citation line** (methods/appendix):
> Densitometry was performed with WB_quantifier v1.0.0 (https://github.com/camKD98/WB_quantifier, commit `<sha>`), an interactive Python/Tkinter tool; every export records tool version, lane/band geometry, baseline method and region, integration bounds, and — where used — Gaussian fit parameters, enabling re-analysis from the raw TIFF.

**Validation sentence** (appendix):
> The quantification routines were verified against an independent re-implementation of the same method on 16 synthetic and real lane profiles (mean absolute difference 0.007%, maximum 0.11%; `validation/BENCHMARK_REPORT.md`), and 44 unit tests cover profile extraction, all baseline and integration modes, and the Gaussian fit.

**Honest limitation disclosures worth one clause each:**
- Gaussian reconstruction is an *estimate* applied to a user-selected region (not an algorithmically chosen least-distorted segment); the "full" area mode extrapolates beyond bounds.
- Historical exports predate the provenance columns; method settings for legacy CSVs should be re-stated from lab records if challenged.
- Automatic mode quantifies one band per lane; multi-band lanes used interactive mode.

**Backup files — verdict:** the ~20 `wb_quantifier_backup*.py` copies were panic-revert artifacts (the HEAD commit message says as much). Confirmed: every backup's methods are a strict subset of the current file — the newest features (focus handling, Gaussian fitting, empirical LOQ) exist only in `wb_quantifier_advanced.py`. None are needed; all remain in history at `45ec271`.

**Suggested sequence for you:** (1) archive raw data + verify manifest → (2) run the §1.4 release commands → (3) put the real author name in `CITATION.cff` + commit sha in the thesis citation → (4) tag `v1.0.0` → (5) optionally re-quantify 2–3 thesis bands with the released build so the new CSVs carry full provenance.

---

## Appendix — remaining known issues (unfixed, documented)

- `percent_height`/`minimum` baselines are only valid for positive-peak profiles (§3.3).
- Interactive "Finish" discards results unless the user pages past the last lane (results land in `band_data` only on that transition) — workflow quirk, unchanged.
- `wb_quantifier_simple.py` is garbled/vestigial (a second class pasted inside `setup_gui`); `wb_quantifier.py` is the cv2-era v1 — both kept, marked legacy in README.
- `np.trapz` is deprecated in NumPy ≥2.0 (pinned env uses 1.26.4 — fine).
- `Area_raw` is recomputed at export from in-memory profiles — stale if lanes are edited between analysis and export.
- TIFF tag metadata of raw images not inspected (no `exiftool` on this machine).
- `README_ADVANCED.md`, `FEATURES.md`, `BUILD_INSTRUCTIONS.md`, `WINDOWS_BUILD.md` are partially stale (refer to old requirements names / pre-v1.0.0 behavior) — left in place with README as the entry point.
