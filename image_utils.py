"""Image loading utilities.

Provides a TIFF-first loader (tifffile preferred) that returns a displayable
PIL image and reproducible metadata. Also provides helpers to create a
deterministic display image from raw arrays and an export helper to write
PNG/TIFF using the chosen display scaling. The loader does not overwrite
original pixel data; display scaling is non-destructive and configurable.
"""
from PIL import Image
import numpy as np


def normalize_to_uint8(arr, p_low=0.5, p_high=99.5, gamma=1.0):
    """Scale a numeric array to uint8 using percentile clipping and optional
    gamma correction. Returns a uint8 array in the range 0..255.

    p_low/p_high are percentiles (0-100) used for robust clipping.
    """
    if arr.dtype == np.uint8:
        a = arr.astype(np.uint8)
        if gamma != 1.0:
            a = np.power(a.astype(np.float32) / 255.0, gamma) * 255.0
            a = np.clip(a, 0, 255).astype(np.uint8)
        return a

    a = arr.astype(np.float64)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    # compute percentiles for clipping
    try:
        lo = np.nanpercentile(a, p_low)
        hi = np.nanpercentile(a, p_high)
    except Exception:
        lo = float(np.nanmin(a)) if a.size else 0.0
        hi = float(np.nanmax(a)) if a.size else 1.0
    if hi <= lo:
        # fallback to min/max
        lo = float(np.nanmin(a))
        hi = float(np.nanmax(a))
        if hi == lo:
            return np.zeros(a.shape, dtype=np.uint8)

    a = (a - lo) / (hi - lo)
    a = np.clip(a, 0.0, 1.0)
    if gamma != 1.0:
        a = np.power(a, gamma)
    a = (a * 255.0).clip(0, 255)
    return a.astype(np.uint8)


def _to_rgb_array(arr, p_low=0.5, p_high=99.5, gamma=1.0):
    """Return an HxWx3 uint8 RGB array for display from a raw array.

    Handles single-channel or multi-channel arrays.
    """
    # If array is 3D and last dim is channel-like, assume HxWxC
    if arr.ndim == 3 and arr.shape[2] in (3, 4):
        # If channels are not uint8, scale each channel independently using
        # percentiles computed on the full image (preserves relative contrast).
        out = np.empty((arr.shape[0], arr.shape[1], 3), dtype=np.uint8)
        for c in range(3):
            channel = arr[..., c]
            out[..., c] = normalize_to_uint8(channel, p_low=p_low, p_high=p_high, gamma=gamma)
        return out

    # otherwise treat as single-channel
    arr8 = normalize_to_uint8(arr, p_low=p_low, p_high=p_high, gamma=gamma)
    out = np.stack([arr8, arr8, arr8], axis=-1)
    return out


def load_image(path, page=None, return_raw=False, p_low=0.5, p_high=99.5, gamma=1.0):
    """Load image from path using tifffile first, fall back to Pillow.

    Returns (PIL.Image, meta) by default. If return_raw=True returns (arr, meta)
    where arr is a NumPy array for direct quantitative use.

    meta keys: n_pages, page_shapes, dtype, min, max
    """
    # Try tifffile first for robust TIFF handling
    try:
        import tifffile
        with tifffile.TiffFile(path) as tf:
            n_pages = len(tf.pages)
            page_shapes = [p.shape for p in tf.pages]

        # Read requested page (key) if provided; otherwise read first page
        try:
            if page is None:
                arr = tifffile.imread(path)
            else:
                arr = tifffile.imread(path, key=page)
        except Exception:
            # Some tifffile versions return list-like; use TiffFile to read explicit page
            with tifffile.TiffFile(path) as tf:
                if page is None:
                    arr = tf.pages[0].asarray()
                else:
                    arr = tf.pages[page].asarray()

        # If arr is an array with leading page dimension choose first if ambiguous
        if isinstance(arr, list):
            arr = arr[0]
        if getattr(arr, 'ndim', 0) == 3 and arr.shape[0] < 10 and arr.shape[0] != arr.shape[1]:
            # likely (pages, H, W)
            arr = arr[0]

        meta = {
            'n_pages': n_pages,
            'page_shapes': page_shapes,
            'dtype': str(getattr(arr, 'dtype', None))
        }
        try:
            meta['min'] = float(np.nanmin(arr))
            meta['max'] = float(np.nanmax(arr))
        except Exception:
            meta['min'] = None
            meta['max'] = None

        if return_raw:
            return arr, meta

        # Create displayable PIL image using percentile scaling
        display = _to_rgb_array(arr, p_low=p_low, p_high=p_high, gamma=gamma)
        pil = Image.fromarray(display)
        if pil.mode != 'RGB':
            pil = pil.convert('RGB')
        return pil, meta
    except Exception:
        # Fallback to Pillow for non-TIFF or if tifffile is not present
        try:
            img = Image.open(path)
            img.load()
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Minimal metadata when using Pillow
            meta = {
                'n_pages': 1,
                'page_shapes': [img.size[::-1]],
                'dtype': 'uint8',
                'min': 0,
                'max': 255
            }
            if return_raw:
                return np.array(img), meta
            return img, meta
        except Exception as e:
            raise RuntimeError(f'Failed to load image {path}: {e}')



def inspect_tiff(path):
    """Utility to return some stats (for debugging)."""
    import tifffile
    arr = tifffile.imread(path)
    info = {}
    info['shape'] = arr.shape
    info['dtype'] = str(arr.dtype)
    try:
        info['min'] = float(np.nanmin(arr))
        info['max'] = float(np.nanmax(arr))
    except Exception:
        info['min'] = None
        info['max'] = None
    # If tifffile can open pages, include count
    try:
        with tifffile.TiffFile(path) as tf:
            info['n_pages'] = len(tf.pages)
            info['page_shapes'] = [p.shape for p in tf.pages]
    except Exception:
        info['n_pages'] = None
    return info


def export_png(path, outpath, page=0, bitdepth=8, p_low=0.5, p_high=99.5, gamma=1.0):
    """Export the chosen page of `path` to a PNG at `outpath`.

    - bitdepth: 8 or 16. 16 will attempt to scale into uint16 range.
    - p_low/p_high/gamma: display scaling parameters.

    This function is explicit and opt-in; it does not modify the source file.
    """
    # Load raw array via tifffile if available to preserve dtype before scaling
    arr, meta = load_image(path, page=page, return_raw=True, p_low=p_low, p_high=p_high, gamma=gamma)
    # Create scaled image
    if bitdepth == 16:
        # scale to 0..65535
        img8 = _to_rgb_array(arr, p_low=p_low, p_high=p_high, gamma=gamma)
        img16 = (img8.astype(np.uint16) * 257)  # simple upscale 0..255 -> 0..65535
        pil = Image.fromarray(img16, mode='RGB')
    else:
        img8 = _to_rgb_array(arr, p_low=p_low, p_high=p_high, gamma=gamma)
        pil = Image.fromarray(img8, mode='RGB')

    pil.save(outpath)
    return outpath, meta
