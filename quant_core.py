"""Quantification core for the Western Blot Quantifier (GUI-independent).

Pure functions implementing the exact math used by wb_quantifier_advanced.py.
"""
import numpy as np
from scipy import signal
from scipy.optimize import curve_fit


def extract_profile(gray2d, rect):
    """Extract a 1-D intensity profile (mean across width) from a lane rect.

    rect is (x, y, w, h). Returns the row-wise mean of the lane region.
    """
    x, y, w, h = rect
    lane_roi = gray2d[y:y+h, x:x+w]
    return np.mean(lane_roi, axis=1)


def detect_strongest_peak(profile, min_distance=20, bands_are_bright=False):
    """Detect peaks in intensity profile and keep only the strongest."""
    # Respect band polarity: if bands are bright, peaks are high; else invert so dark bands become peaks
    if bands_are_bright:
        data = np.array(profile, dtype=np.float64)
    else:
        data = np.array(-profile, dtype=np.float64)

    # Use a relative prominence (5% of data range) to work with small float profiles
    data_range = np.nanmax(data) - np.nanmin(data)
    prom = max(data_range * 0.05, 1e-8)

    # Find peaks
    peaks, properties = signal.find_peaks(data, distance=min_distance, prominence=prom)

    # Keep only the single strongest peak (by prominence, fallback to peak height)
    if len(peaks) > 1:
        prominences = properties.get('prominences') if 'prominences' in properties else None
        if prominences is None:
            # compute simple peak heights from data
            peak_vals = data[peaks]
            best_idx = int(np.argmax(np.abs(peak_vals)))
        else:
            best_idx = int(np.argmax(prominences))
        peaks = np.array([peaks[best_idx]])
        # filter properties arrays to only the selected peak where possible
        for k, v in list(properties.items()):
            try:
                properties[k] = np.array([v[best_idx]])
            except Exception:
                pass

    return peaks, properties


def compute_background_baselines(arr, background_boxes, background_lane_map=None, n_lanes=None):
    """Compute robust (median) background baseline values from BG boxes."""
    if arr is None or len(background_boxes) == 0:
        return {'global': None, 'per_lane': {}}

    if background_lane_map is None:
        background_lane_map = []

    if n_lanes is None:
        mapped = [m for m in background_lane_map if m is not None]
        n_lanes = (max(mapped) + 1) if mapped else 0

    all_segments = []
    lane_segments = {i: [] for i in range(n_lanes)}

    for idx, (x, y, w, h) in enumerate(background_boxes):
        y1 = max(0, int(y))
        y2 = min(arr.shape[0], int(y + h))
        x1 = max(0, int(x))
        x2 = min(arr.shape[1], int(x + w))
        if y2 <= y1 or x2 <= x1:
            continue

        pixels = arr[y1:y2, x1:x2].flatten()
        if len(pixels) == 0:
            continue
        all_segments.append(pixels)

        lane_idx = background_lane_map[idx] if idx < len(background_lane_map) else None
        if lane_idx is not None and lane_idx in lane_segments:
            lane_segments[lane_idx].append(pixels)

    if len(all_segments) == 0:
        return {'global': None, 'per_lane': {}}

    global_baseline = float(np.median(np.concatenate(all_segments)))
    per_lane = {}
    for lane_idx, chunks in lane_segments.items():
        if len(chunks) == 0:
            continue
        per_lane[lane_idx] = float(np.median(np.concatenate(chunks)))

    return {'global': global_baseline, 'per_lane': per_lane}


def calculate_baseline(profile, method='minimum', lane_idx=None, bg_baselines=None,
                       bands_are_bright=False):
    """Calculate baseline for profile."""
    if method == 'none':
        # Keep backward compatibility with old configs; treat as minimum.
        method = 'minimum'
    if method == 'manual_region':
        # Manual region baseline is handled in interactive mode per-band.
        # Fallback to minimum for non-interactive callers.
        method = 'minimum'
    if method == 'background_boxes':
        if bg_baselines is None:
            bg_baselines = {}
        baseline_value = None
        if lane_idx is not None:
            baseline_value = bg_baselines.get('per_lane', {}).get(lane_idx)
        if baseline_value is None:
            baseline_value = bg_baselines.get('global')
        if baseline_value is None:
            # Fallback when no BG boxes are available
            baseline_value = float(np.min(profile))
        return np.full_like(profile, baseline_value, dtype=np.float64)
    if method == 'minimum':
        return np.full_like(profile, np.min(profile))
    elif method == 'linear':
        # Fit line to background points (choose top or bottom 10% based on polarity)
        n = max(3, len(profile) // 10)
        # NOTE: the original code had an if/else on bands_are_bright with identical
        # bodies (both branches pick the top-n indices); collapsed to a single path.
        idx = np.argsort(profile)[-n:]

        x = np.arange(len(profile), dtype=np.float64)
        y = np.array(profile, dtype=np.float64)[idx]
        xi = np.array(idx, dtype=np.float64)

        # Defensive: if not enough distinct points, return constant baseline
        try:
            if len(xi) >= 2 and np.ptp(y) != 0:
                z = np.polyfit(xi, y, 1)
                baseline = np.polyval(z, x)
            else:
                baseline = np.full_like(profile, np.median(y) if len(y) > 0 else 0.0)
        except Exception:
            baseline = np.full_like(profile, np.median(y) if len(y) > 0 else 0.0)

        return baseline
    return np.zeros_like(profile)


def median_region_value(profile, start, end):
    """Median baseline value for a manually selected region (clamped ints)."""
    b_start = max(0, min(int(start), len(profile) - 1))
    b_end = max(0, min(int(end), len(profile)))
    if b_end <= b_start:
        return float(np.median(profile))
    return float(np.median(profile[b_start:b_end]))


def median_region_baseline(profile, start, end):
    """Flat baseline array at the median of the manually selected region."""
    baseline_value = median_region_value(profile, start, end)
    return np.full_like(profile, baseline_value, dtype=np.float64)


def integrate_peak(corrected, peak_idx, method='fixed_width', width=None, threshold=0.1):
    """Integrate area under peak on an already-baseline-corrected profile."""
    if method == 'fixed_width' and width is not None:
        # Use fixed width centered on peak
        half_width = width // 2
        start = max(0, peak_idx - half_width)
        end = min(len(corrected), peak_idx + half_width)

    elif method == 'percent_height':
        # Find boundaries at threshold % of peak height
        peak_height = corrected[peak_idx]
        threshold_value = peak_height * threshold

        # Find left boundary
        start = peak_idx
        while start > 0 and corrected[start] > threshold_value:
            start -= 1

        # Find right boundary
        end = peak_idx
        while end < len(corrected) - 1 and corrected[end] > threshold_value:
            end += 1
    elif method == 'full_profile':
        # In whole-lane mode, quantify only the dominant peak above baseline.
        if len(corrected) == 0:
            start, end = 0, 0
        else:
            if np.nanmax(corrected) < abs(np.nanmin(corrected)):
                corrected = -corrected

            peak_idx = int(np.argmax(corrected))
            if corrected[peak_idx] <= 0:
                start = max(0, peak_idx)
                end = min(len(corrected), peak_idx + 1)
            else:
                start = peak_idx
                while start > 0 and corrected[start] > 0:
                    start -= 1
                if corrected[start] <= 0:
                    start += 1

                end = peak_idx
                while end < len(corrected) - 1 and corrected[end] > 0:
                    end += 1
                if corrected[end] <= 0:
                    end -= 1
                end = min(len(corrected), end + 1)
    else:
        # Default to full profile
        start = 0
        end = len(corrected)

    # Calculate area (ensure positive area)
    area = np.trapz(corrected[start:end])
    peak_height = corrected[peak_idx]
    if area < 0:
        area = -area
        peak_height = -peak_height
    width_pixels = end - start

    return {
        'area': area,
        'height': peak_height,
        'width': width_pixels,
        'start': start,
        'end': end,
        'peak_position': peak_idx
    }


def estimate_band_width(corrected, peak_idx, threshold=0.2):
    """Estimate band width at a fraction of peak height (corrected profile)."""
    peak_height = corrected[peak_idx]
    threshold_value = peak_height * threshold

    # Find width at threshold
    left = peak_idx
    while left > 0 and corrected[left] > threshold_value:
        left -= 1

    right = peak_idx
    while right < len(corrected) - 1 and corrected[right] > threshold_value:
        right += 1

    width = right - left
    return width


def gaussian(x, amp, mu, sigma):
    sigma = np.maximum(sigma, 1e-6)
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2)


def fit_single_peak_gaussian(x_vals, y_vals):
    """Fit a single Gaussian to a selected corrected-signal region."""
    if len(x_vals) < 5 or len(y_vals) < 5:
        return None

    x_vals = np.array(x_vals, dtype=np.float64)
    y_vals = np.array(y_vals, dtype=np.float64)

    # Work in positive-peak space for fitting, keep polarity for reconstruction.
    if np.nanmax(y_vals) >= abs(np.nanmin(y_vals)):
        fit_polarity = 1.0
        y_fit = np.maximum(y_vals, 0.0)
    else:
        fit_polarity = -1.0
        y_fit = np.maximum(-y_vals, 0.0)

    if not np.isfinite(y_fit).all() or np.nanmax(y_fit) <= 0:
        return None

    peak_idx = int(np.argmax(y_fit))
    mu0 = float(x_vals[peak_idx])
    amp0 = float(y_fit[peak_idx])
    width = max(2.0, float(x_vals[-1] - x_vals[0]))
    sigma0 = max(1.5, width / 6.0)

    try:
        popt, _ = curve_fit(
            gaussian,
            x_vals,
            y_fit,
            p0=[amp0, mu0, sigma0],
            bounds=(
                [0.0, float(x_vals[0] - width), 0.5],
                [np.inf, float(x_vals[-1] + width), max(2.0, 4.0 * width)]
            ),
            maxfev=5000,
        )
    except Exception:
        return None

    amp, mu, sigma = [float(v) for v in popt]
    y_fit_model = gaussian(x_vals, amp, mu, sigma)
    y_signed_model = y_fit_model * fit_polarity
    selected_area = float(abs(np.trapz(y_fit_model, x_vals)))
    full_area = float(abs(amp * sigma * np.sqrt(2.0 * np.pi)))

    fit_peak_position = int(round(mu))
    fit_peak_position = max(int(x_vals[0]), min(int(x_vals[-1]), fit_peak_position))
    fit_peak_height = float(abs(y_fit_model[np.argmax(y_fit_model)]))

    return {
        'selected_area': selected_area,
        'full_area': full_area,
        'peak_position': fit_peak_position,
        'peak_height': fit_peak_height,
        'amp': amp,
        'mu': mu,
        'sigma': sigma,
        'polarity': fit_polarity,
        'x': x_vals,
        'y_signed': y_signed_model,
    }
