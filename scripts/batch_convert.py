"""Batch convert multi-page Image Studio TIFFs to PNG using image_utils.

Usage:
  PYTHONPATH=. python3 scripts/batch_convert.py input_dir output_dir

This will search recursively for TIF/TIFF files and write _page0.png for each file
(or _pageN.png for each page if --all-pages is specified.
"""
import sys
import os
from image_utils import load_image, inspect_tiff
from PIL import Image


def convert_file(path, out_dir, all_pages=False):
    rel = os.path.relpath(path)
    base = os.path.splitext(os.path.basename(path))[0]
    try:
        info = inspect_tiff(path)
    except Exception:
        info = None
    if all_pages and info and info.get('n_pages', 1) > 1:
        for p in range(info['n_pages']):
            try:
                img, meta = load_image(path, page=p)
                out_path = os.path.join(out_dir, f"{base}_page{p}.png")
                img.save(out_path)
                print('Wrote', out_path)
            except Exception as e:
                print('Failed', path, p, e)
    else:
        try:
            img, meta = load_image(path)
            out_path = os.path.join(out_dir, f"{base}.png")
            img.save(out_path)
            print('Wrote', out_path)
        except Exception as e:
            print('Failed', path, e)


def main():
    if len(sys.argv) < 3:
        print('Usage: PYTHONPATH=. python3 scripts/batch_convert.py input_dir output_dir [--all-pages]')
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2]
    allp = '--all-pages' in sys.argv
    os.makedirs(out, exist_ok=True)
    for root, dirs, files in os.walk(inp):
        for f in files:
            if f.lower().endswith(('.tif', '.tiff')):
                convert_file(os.path.join(root, f), out, all_pages=allp)

if __name__ == '__main__':
    main()
