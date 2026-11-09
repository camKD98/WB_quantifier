from image_utils import load_image, inspect_tiff

paths = [
    'raw_image_studio/22_12_25_wb_t-fak recover/0001883_01/0001883_01_Chemi.TIF',
    'raw_image_studio/allwbresultsup224thoct/0001773_01/0001773_01_Chemi.TIF'
]

for p in paths:
    try:
        info = inspect_tiff(p)
        print('inspect_tiff:', p, info)
    except Exception as e:
        print('inspect_tiff failed for', p, e)
    try:
        result = load_image(p)
        if isinstance(result, tuple):
            img, meta = result
            print('Loaded', p, '->', img.size, img.mode, 'meta:', meta)
        else:
            img = result
            print('Loaded', p, '->', img.size, img.mode)
    except Exception as e:
        print('load_image failed for', p, e)
