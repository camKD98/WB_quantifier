from PIL import Image, TiffImagePlugin
import numpy as np
import sys
import tifffile

path = sys.argv[1]

print('Inspecting:', path)

# Try with Pillow
try:
    img = Image.open(path)
    print('Pillow mode:', img.mode)
    print('Pillow size:', img.size)
    try:
        print('Pillow tags:')
        for k, v in img.tag_v2.items():
            print(' ', k, v)
    except Exception as e:
        print('  (failed to read tags)', e)
    arr = np.array(img)
    print('Pillow array shape:', arr.shape, 'dtype:', arr.dtype)
    print('min/max:', arr.min(), arr.max())
except Exception as e:
    print('Pillow failed:', e)

# Try with tifffile
try:
    tif = tifffile.imread(path)
    print('tifffile shape:', tif.shape, 'dtype:', tif.dtype)
    print('min/max:', tif.min(), tif.max())
    try:
        with tifffile.TiffFile(path) as tf:
            print('Number of pages:', len(tf.pages))
            for i, page in enumerate(tf.pages):
                print(' page', i, 'shape', page.shape, 'dtype', page.dtype)
    except Exception as e:
        print('tifffile pages failed:', e)
except Exception as e:
    print('tifffile failed:', e)
