"""Ground-truth tests for the pure-math quantification core."""
import numpy as np
import pytest

import quant_core as qc
from conftest import gaussian_profile, flat_bg


# ---------------------------------------------------------------- extract_profile

def test_extract_profile_row_means():
    arr = np.array([
        [0, 10, 20],
        [30, 40, 50],
        [60, 70, 80],
        [90, 100, 110],
    ], dtype=np.float64)
    # rect (x=0, y=1, w=3, h=2) -> rows 1..2, all cols
    prof = qc.extract_profile(arr, (0, 1, 3, 2))
    np.testing.assert_allclose(prof, [40.0, 70.0])
    # sub-rect in x: columns 1..2 of rows 0..3
    prof2 = qc.extract_profile(arr, (1, 0, 2, 4))
    np.testing.assert_allclose(prof2, [15.0, 45.0, 75.0, 105.0])


# ---------------------------------------------------------------- detect_strongest_peak

def test_detect_strongest_peak_picks_largest():
    x = np.arange(200)
    profile = gaussian_profile(x, 100, 50, 8) + gaussian_profile(x, 60, 150, 5)
    peaks, props = qc.detect_strongest_peak(profile, min_distance=20,
                                          bands_are_bright=True)
    assert list(peaks) == [50]


def test_detect_strongest_peak_dark_bands():
    x = np.arange(200)
    # dark bands: dips in a bright background
    profile = 200 - gaussian_profile(x, 100, 50, 8) - gaussian_profile(x, 60, 150, 5)
    peaks, _ = qc.detect_strongest_peak(profile, min_distance=20,
                                        bands_are_bright=False)
    assert list(peaks) == [50]


def test_detect_strongest_peak_rejects_shoulder():
    x = np.arange(120)
    # dominant peak plus a tiny shoulder that must not be returned
    profile = gaussian_profile(x, 100, 60, 8) + gaussian_profile(x, 2, 75, 2)
    peaks, _ = qc.detect_strongest_peak(profile, min_distance=20,
                                        bands_are_bright=True)
    assert len(peaks) == 1
    assert peaks[0] == 60


def test_detect_strongest_peak_min_distance_merges_close_peaks():
    x = np.arange(100)
    # two equal peaks closer than min_distance: find_peaks keeps the first
    profile = gaussian_profile(x, 50, 40, 3) + gaussian_profile(x, 50, 45, 3)
    peaks_far, _ = qc.detect_strongest_peak(profile, min_distance=20,
                                            bands_are_bright=True)
    assert len(peaks_far) == 1  # merged by distance then strongest kept


# ---------------------------------------------------------------- compute_background_baselines

def test_compute_background_baselines_exact():
    arr = np.zeros((20, 20))
    arr[0:5, 0:5] = 10.0    # region A
    arr[10:15, 10:15] = 40.0  # region B
    boxes = [(0, 0, 5, 5), (10, 10, 5, 5)]
    lane_map = [0, 1]
    res = qc.compute_background_baselines(arr, boxes, lane_map, n_lanes=2)
    assert res['global'] == pytest.approx(np.median([10.0] * 25 + [40.0] * 25))
    assert res['per_lane'][0] == pytest.approx(10.0)
    assert res['per_lane'][1] == pytest.approx(40.0)


def test_compute_background_baselines_none_map_in_global_only():
    arr = np.zeros((20, 20))
    arr[0:5, 0:5] = 10.0
    arr[10:15, 10:15] = 40.0
    boxes = [(0, 0, 5, 5), (10, 10, 5, 5)]
    res = qc.compute_background_baselines(arr, boxes, [0, None], n_lanes=2)
    # second box excluded from per_lane but counted in global
    assert res['per_lane'] == {0: pytest.approx(10.0)}
    assert res['global'] == pytest.approx(np.median([10.0] * 25 + [40.0] * 25))


def test_compute_background_baselines_empty():
    arr = np.zeros((10, 10))
    assert qc.compute_background_baselines(arr, []) == {'global': None, 'per_lane': {}}
    assert qc.compute_background_baselines(None, [(0, 0, 2, 2)]) == {'global': None, 'per_lane': {}}


# ---------------------------------------------------------------- calculate_baseline

def test_calculate_baseline_minimum():
    profile = np.array([5.0, 2.0, 9.0, 3.0])
    bl = qc.calculate_baseline(profile, 'minimum')
    np.testing.assert_allclose(bl, np.full_like(profile, 2.0))


def test_calculate_baseline_background_boxes_priority():
    profile = np.arange(10, dtype=np.float64)
    bg = {'global': 42.0, 'per_lane': {1: 7.5}}
    # per-lane wins when lane_idx is mapped
    np.testing.assert_allclose(
        qc.calculate_baseline(profile, 'background_boxes', lane_idx=1, bg_baselines=bg),
        np.full_like(profile, 7.5))
    # global fallback when lane not mapped
    np.testing.assert_allclose(
        qc.calculate_baseline(profile, 'background_boxes', lane_idx=0, bg_baselines=bg),
        np.full_like(profile, 42.0))
    # min(profile) fallback when nothing available
    np.testing.assert_allclose(
        qc.calculate_baseline(profile, 'background_boxes', lane_idx=3,
                              bg_baselines={'global': None, 'per_lane': {}}),
        np.full_like(profile, np.min(profile)))


def test_calculate_baseline_remaps_to_minimum():
    profile = np.array([4.0, 1.0, 8.0])
    for method in ('manual_region', 'none'):
        np.testing.assert_allclose(
            qc.calculate_baseline(profile, method), np.full_like(profile, 1.0))


def test_calculate_baseline_linear_on_dipped_background():
    x = np.arange(200)
    profile = flat_bg(200, 100.0) - gaussian_profile(x, 60, 100, 5)
    bl = qc.calculate_baseline(profile, 'linear', bands_are_bright=False)
    # top-decile fit should recover ~flat 100 background
    assert np.abs(np.mean(bl) - 100.0) < 2.0
    assert np.std(bl) < 1.0


def test_calculate_baseline_unknown_returns_zeros():
    profile = np.arange(10, dtype=np.float64)
    np.testing.assert_allclose(
        qc.calculate_baseline(profile, 'bogus_method'), np.zeros_like(profile))


# ---------------------------------------------------------------- median_region_*

def test_median_region_value():
    profile = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert qc.median_region_value(profile, 1, 4) == pytest.approx(3.0)


def test_median_region_value_empty_window_falls_back():
    profile = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    # start >= end -> median of whole profile
    assert qc.median_region_value(profile, 3, 3) == pytest.approx(3.0)
    profile2 = np.array([10.0, 0.0, 20.0])
    assert qc.median_region_value(profile2, 2, 1) == pytest.approx(10.0)


def test_median_region_baseline_flat():
    profile = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    bl = qc.median_region_baseline(profile, 0, 3)
    np.testing.assert_allclose(bl, np.full_like(profile, 2.0))


# ---------------------------------------------------------------- integrate_peak

def test_integrate_peak_fixed_width_gaussian_area():
    x = np.arange(400)
    amp, mu, sigma = 80.0, 200.0, 6.0
    corrected = gaussian_profile(x, amp, mu, sigma)  # baseline already removed
    k = int(6 * sigma)
    res = qc.integrate_peak(corrected, int(mu), method='fixed_width', width=2 * k + 1)
    expected = amp * sigma * np.sqrt(2 * np.pi)
    assert res['area'] == pytest.approx(expected, rel=0.02)
    assert res['start'] == mu - k
    assert res['end'] == mu + k
    assert res['peak_position'] == int(mu)
    assert res['height'] == pytest.approx(amp, rel=1e-6)


def test_integrate_peak_fixed_width_edge_clamp():
    corrected = np.array([3.0, 4.0, 5.0, 4.0, 3.0, 1.0, 0.5])
    res = qc.integrate_peak(corrected, 2, method='fixed_width', width=9)
    # half_width=4 -> start=max(0,-2)=0, end=min(7,6)=6
    assert res['start'] == 0
    assert res['end'] == 6
    assert res['area'] == pytest.approx(float(np.trapz(corrected[0:6])))


def test_integrate_peak_percent_height_triangle():
    # triangle ramp 0..10..0, peak value 10 at index 10
    corrected = np.array(list(range(11)) + list(range(9, -1, -1)), dtype=np.float64)
    res = qc.integrate_peak(corrected, 10, method='percent_height', threshold=0.1)
    # threshold_value = 1.0; walks stop at first point <= 1.0 on each side
    assert res['start'] == 1   # corrected[1] == 1.0 (not > 1.0)
    assert res['end'] == 19    # corrected[19] == 1.0
    assert res['area'] == pytest.approx(float(np.trapz(corrected[1:19])))


def test_integrate_peak_full_profile_covers_positive_lobe():
    x = np.arange(300)
    amp, mu, sigma = 50.0, 150.0, 5.0
    corrected = gaussian_profile(x, amp, mu, sigma) - 1.0  # tails below zero
    res = qc.integrate_peak(corrected, int(mu), method='full_profile')
    # boundaries should sit at the zero crossings around the lobe
    cross = sigma * np.sqrt(-2 * np.log(1.0 / amp))  # where G = 1.0
    assert abs(res['start'] - (mu - cross)) <= 2
    assert abs(res['end'] - (mu + cross)) <= 2
    assert res['area'] > 0


def test_integrate_peak_unknown_method_whole_profile():
    corrected = np.array([1.0, 2.0, 3.0, 2.0])
    res = qc.integrate_peak(corrected, 2, method='bogus')
    assert res['start'] == 0
    assert res['end'] == len(corrected)
    assert res['area'] == pytest.approx(float(np.trapz(corrected)))


def test_integrate_peak_negative_dip_flips_area():
    corrected = -gaussian_profile(np.arange(100), 40.0, 50.0, 4.0)
    res = qc.integrate_peak(corrected, 50, method='bogus')
    assert res['area'] == pytest.approx(abs(float(np.trapz(corrected))), rel=1e-9)
    assert res['height'] > 0


# ---------------------------------------------------------------- estimate_band_width

def test_estimate_band_width_gaussian():
    x = np.arange(400)
    sigma = 4.0
    corrected = gaussian_profile(x, 100.0, 200.0, sigma)
    width = qc.estimate_band_width(corrected, 200, threshold=0.2)
    expected = 2 * sigma * np.sqrt(2 * np.log(5.0))  # width at 20% height
    assert abs(width - expected) <= 2


# ---------------------------------------------------------------- fit_single_peak_gaussian

def test_fit_single_peak_gaussian_recovers_params():
    x = np.arange(0, 200, dtype=np.float64)
    amp, mu, sigma = 75.0, 100.0, 7.0
    y = gaussian_profile(x, amp, mu, sigma)  # noiseless, offset already removed
    res = qc.fit_single_peak_gaussian(x, y)
    assert res is not None
    assert res['amp'] == pytest.approx(amp, rel=0.01)
    assert res['mu'] == pytest.approx(mu, rel=0.01)
    assert res['sigma'] == pytest.approx(sigma, rel=0.01)
    assert res['full_area'] == pytest.approx(amp * sigma * np.sqrt(2 * np.pi), rel=0.01)
    assert res['selected_area'] <= res['full_area'] + 1e-9
    assert res['polarity'] == 1.0
    assert res['peak_position'] == int(round(mu))


def test_fit_single_peak_gaussian_too_few_points():
    x = np.arange(4, dtype=np.float64)
    y = gaussian_profile(x, 10, 2, 1)
    assert qc.fit_single_peak_gaussian(x, y) is None


def test_fit_single_peak_gaussian_zero_input():
    x = np.arange(50, dtype=np.float64)
    assert qc.fit_single_peak_gaussian(x, np.zeros(50)) is None


def test_fit_single_peak_gaussian_negative_dip_polarity():
    x = np.arange(0, 200, dtype=np.float64)
    y = -gaussian_profile(x, 60.0, 100.0, 6.0)
    res = qc.fit_single_peak_gaussian(x, y)
    assert res is not None
    assert res['polarity'] == -1.0
    assert res['amp'] == pytest.approx(60.0, rel=0.01)


# ---------------------------------------------------------------- gaussian

def test_gaussian_spot_values():
    assert qc.gaussian(0.0, 5.0, 0.0, 2.0) == pytest.approx(5.0)
    assert qc.gaussian(2.0, 5.0, 0.0, 2.0) == pytest.approx(5.0 * np.exp(-0.5))
    np.testing.assert_allclose(
        qc.gaussian(np.array([0.0, 4.0]), 1.0, 2.0, 2.0),
        [np.exp(-0.5), np.exp(-0.5)])
