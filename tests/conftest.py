"""Shared fixtures/builders for the WB_quantifier test suite.

All tests run headless: the app is instantiated via __new__ (no Tk root)
with stub vars injected.
"""
import os
import sys
import types

import numpy as np
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import wb_quantifier_advanced  # noqa: E402
from wb_quantifier_advanced import WesternBlotQuantifier  # noqa: E402


def gaussian_profile(x, amp, mu, sigma):
    """Synthetic Gaussian intensity profile."""
    x = np.asarray(x, dtype=np.float64)
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2)


def flat_bg(n, level):
    """Flat background array of length n at the given level."""
    return np.full(int(n), float(level), dtype=np.float64)


def stub_var(v):
    """Stand-in for tk.Variable supporting .get()."""
    return types.SimpleNamespace(get=lambda: v)


def bare_app(**overrides):
    """A WesternBlotQuantifier with no Tk root and stub attributes injected."""
    app = WesternBlotQuantifier.__new__(WesternBlotQuantifier)
    app.bands_are_bright = stub_var(False)
    app.invert_image_var = stub_var(False)
    app.baseline_method = stub_var('minimum')
    app.integration_method = stub_var('fixed_width')
    app.peak_threshold = stub_var(0.1)
    app.lanes = []
    app.lane_size = None
    app.background_boxes = []
    app.background_lane_map = []
    app.original_image = None
    app.image_path = None
    app.image_page = 0
    app.lane_profiles = []
    app.band_data = []
    app.reference_band_width = None
    for k, v in overrides.items():
        setattr(app, k, v)
    return app


@pytest.fixture
def app():
    return bare_app()
