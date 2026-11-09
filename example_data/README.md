# Synthetic example dataset

`synthetic_blot.tif` is a programmatically generated 1200x400 uint16 grayscale
image that mimics a fluorescent Western blot: 8 lanes containing a mix of clean
Gaussian bands of varying intensity, one faint band, one smeared/tailed band,
and one lane with a doublet. `synthetic_blot_lanes.json` is a matching lane
configuration in the app's `save_lane_config` schema so the dataset can be
loaded and quantified end-to-end for demos, tutorials, and regression testing.
It is fully synthetic — no real experimental data is included.

Regenerate deterministically (fixed seed) with:

    python3.12 example_data/generate_synthetic_blot.py
