"""Prove the GUI adapter methods delegate to quant_core identically.

Runs headless via bare_app() — no Tk root is created.
"""
import numpy as np
import pytest

import quant_core as qc
from conftest import bare_app, gaussian_profile, stub_var


def _seeded_profiles():
    rng = np.random.RandomState(1234)
    profiles = []
    for i in range(3):
        x = np.arange(160)
        p = 20.0 + 5.0 * i + gaussian_profile(x, 60 + 10 * i, 60 + 20 * i, 6)
        p = p + rng.normal(0, 0.5, size=x.shape)
        profiles.append(p)
    return profiles


def test_detect_peaks_matches_quant_core():
    app = bare_app()
    for profile in _seeded_profiles():
        app_peaks, app_props = app.detect_peaks(profile, min_distance=15)
        qc_peaks, qc_props = qc.detect_strongest_peak(
            profile, min_distance=15, bands_are_bright=False)
        np.testing.assert_array_equal(app_peaks, qc_peaks)
        for k in qc_props:
            np.testing.assert_allclose(np.asarray(app_props[k], dtype=float),
                                       np.asarray(qc_props[k], dtype=float))


def test_detect_peaks_bright_polarity_matches():
    app = bare_app(bands_are_bright=stub_var(True))
    for profile in _seeded_profiles():
        app_peaks, _ = app.detect_peaks(profile)
        qc_peaks, _ = qc.detect_strongest_peak(profile, bands_are_bright=True)
        np.testing.assert_array_equal(app_peaks, qc_peaks)


def test_calculate_baseline_minimum_matches():
    app = bare_app()
    for profile in _seeded_profiles():
        np.testing.assert_allclose(
            app.calculate_baseline(profile, 'minimum'),
            qc.calculate_baseline(profile, 'minimum'))


def test_calculate_baseline_background_boxes_matches():
    # synthetic raw array: two BG regions mapped to two lanes
    arr = np.zeros((30, 30))
    arr[0:6, 0:6] = 12.0
    arr[20:26, 20:26] = 48.0
    app = bare_app(
        lanes=[(0, 0, 4, 20), (10, 0, 4, 20)],
        background_boxes=[(0, 0, 6, 6), (20, 20, 6, 6)],
        background_lane_map=[0, 1],
    )
    # inject bg_baselines via the app's own helper (arr passed explicitly -> no image I/O)
    bg = app._compute_background_baselines(arr=arr)
    assert bg == qc.compute_background_baselines(
        arr, app.background_boxes, app.background_lane_map, len(app.lanes))
    for profile in _seeded_profiles():
        for lane_idx in (0, 1):
            np.testing.assert_allclose(
                app.calculate_baseline(profile, 'background_boxes',
                                       lane_idx=lane_idx, bg_baselines=bg),
                qc.calculate_baseline(profile, 'background_boxes',
                                      lane_idx=lane_idx, bg_baselines=bg))


@pytest.mark.parametrize('method', ['fixed_width', 'percent_height', 'full_profile'])
def test_integrate_peak_matches_quant_core(method):
    app = bare_app(baseline_method=stub_var('minimum'))
    for profile in _seeded_profiles():
        peak_idx = int(np.argmax(profile))
        app_res = app.integrate_peak(profile, peak_idx, method=method, width=15)
        baseline = qc.calculate_baseline(profile, 'minimum')
        corrected = profile - baseline
        qc_res = qc.integrate_peak(corrected, peak_idx, method=method, width=15)
        assert app_res['area'] == pytest.approx(qc_res['area'], rel=1e-9)
        assert app_res['start'] == qc_res['start']
        assert app_res['end'] == qc_res['end']
        assert app_res['width'] == qc_res['width']
        assert app_res['peak_position'] == qc_res['peak_position']
        assert app_res['height'] == pytest.approx(qc_res['height'], rel=1e-9)


def test_estimate_band_width_matches_quant_core():
    app = bare_app(baseline_method=stub_var('minimum'))
    for profile in _seeded_profiles():
        peak_idx = int(np.argmax(profile))
        baseline = qc.calculate_baseline(profile, 'minimum')
        expected = qc.estimate_band_width(profile - baseline, peak_idx, 0.2)
        assert app.estimate_band_width(profile, peak_idx, 0.2) == expected
