# WB_quantifier

An interactive Western blot densitometry tool. `wb_quantifier_advanced.py` provides a Tkinter/Matplotlib GUI for per-lane ROI analysis: draw lane and background regions on a blot image, generate 1-D intensity profiles, apply a local baseline, choose integration bounds (user-defined or automatic), and quantify band areas by trapezoidal integration — with optional constrained single-peak Gaussian reconstruction. Results are exported to a version-stamped CSV with full analysis provenance. Developed for quantification of HUVEC pFAK(Tyr397)/total-FAK/actin blots.

## Features

- Interactive lane and background-box ROI drawing (with multi-lane auto-generation)
- Save/load lane configurations as JSON for reproducible layouts across blots
- Baseline modes: minimum, background-box median, or manual region
- Integration modes: fixed width (reference), peak-% height, dominant-peak, interactive selection
- Optional constrained single-peak Gaussian reconstruction (interactive)
- LOQ/SNR columns in output
- Provenance- and version-stamped CSV export; high-resolution plot export (PNG/PDF)

## Installation

Python ≥ 3.10 recommended (developed on 3.12):

```bash
pip install -r requirements.txt
```

## Usage

```bash
python wb_quantifier_advanced.py
```

The GUI requires a display; it cannot run fully headless.

Typical workflow:

1. Load a blot image (`.tif`/`.TIF`).
2. Draw lane ROIs (draw the first lane, then auto-add the rest); optionally draw background boxes.
3. Choose baseline and integration settings, then click **Analyze**.
4. **Export CSV** — the output records per-lane areas plus provenance metadata.
5. Use **Save Lane Configuration** to reuse the exact lane layout on other blots.

## Tests and validation

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

See `validation/` for the benchmark supplement.

## Building a standalone executable

PyInstaller-based builds are described in `BUILD_INSTRUCTIONS.md`, `WINDOWS_BUILD.md`, and `build_executable.sh`.

## Legacy and auxiliary files

- `wb_quantifier.py` — original v1 (requires `opencv-python`, not in `requirements.txt`); kept for reference.
- `wb_quantifier_simple.py` — minimal version without scipy; kept for reference.
- `tiff_lossless_rotator_gui.py` — standalone lossless TIFF rotation utility.
- `scripts/` — helper scripts.

## Citation

If you use this software, please cite it — see `CITATION.cff` or the "Cite this repository" button on GitHub.

## License

MIT — see `LICENSE`.

## Data

Raw blot image data are archived separately from this repository; integrity checksums are recorded in `ARCHIVAL_MANIFEST.sha256`.
