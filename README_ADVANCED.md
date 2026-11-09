# Western Blot Quantifier - Advanced Version
### 2. Set Reference Band Width (RECOMMENDED for Method A)
- Click **"Set Reference Band"** button
- Choose a lane that has a clean band (no tailing)
- Click and drag across the clean band to select its width
- The green highlighted area shows your selection
- Click **"Apply Width"** to use this as the reference

**Why do this?** 
- Gives you control over which band is used as the reference
- Ensures you select a clean band without tailing
- This width will be applied symmetrically to all bands, ignoring tails
- **Saved with lane configuration** for future use!

### 3. Choose Quantification Settingsrt Guide

### Installation
```bash
pip3 install -r requirements_advanced.txt
python3 wb_quantifier_advanced.py
```

## Workflow

### 1. Load Image & Define Lanes

**Option A: Draw lanes manually**
- Click "Load Image" and select your Western blot
- Draw the first rectangle (this sets the size for all lanes)
- Click and drag to add more lanes individually
- Use arrow keys to fine-tune positions

**Option B: Add multiple lanes automatically (NEW!)**
- Draw the first lane to set the size
- Click **"Add Multiple Lanes"**
- Specify:
  - Number of lanes (e.g., 12 for a full gel)
  - Spacing between lanes (in pixels)
  - Direction (horizontal or vertical)
  - Starting position
- Lanes are created automatically!

**Option C: Load saved configuration (NEW!)**
- File → **Load Lane Configuration**
- Select a previously saved .json file
- All lanes are restored instantly (no redrawing needed!)

### 2. Save Your Lane Configuration (IMPORTANT!)

Once you've positioned your lanes:
- File → **Save Lane Configuration**
- Saves a .json file with:
  - All lane positions
  - Reference band width (if set)
  - Image dimensions (for validation)
- **Reuse this for similar images** - huge time saver!

### 3. Set Reference Band Width (RECOMMENDED for Method A)
- Click **"Set Reference Band"** button
- Choose a lane that has a clean band (no tailing)
- Click and drag across the clean band to select its width
- The green highlighted area shows your selection
- Click **"Apply Width"** to use this as the reference

**Why do this?** 
- Gives you control over which band is used as the reference
- Ensures you select a clean band without tailing
- This width will be applied symmetrically to all bands, ignoring tails

### 3. Choose Quantification Settings

**Integration Method:**
- **Fixed Width (Reference)** - Best for tailing bands
  - Uses the reference width you set (or auto-detects from first peak)
  - Centers width on each detected peak
  - Ignores asymmetric tailing
  
- **Peak % Height** - Adaptive method
  - Integrates until signal drops to X% of peak height
  - Adjustable threshold (5-50%)
  - Can capture tails if desired
  
- **Interactive Selection** - Manual control
  - Click and drag to select each band boundary
  - Maximum flexibility
  - Good for validation

**Baseline Correction:**
- **Linear** - Best for gradients (fits line through lowest 10% of values)
- **Minimum** - Simple (uses minimum value as baseline)
- **None** - No correction

### 4. Analyze Bands
- Click **"Analyze Bands"**
- Review the plots:
  - Blue line = raw profile
  - Green dashed = baseline
  - Red line = corrected profile
  - Red dots = detected peaks
  - Yellow shading = integration area
  - Numbers = calculated area

### 5. Export Data
- Click **"Export Data (CSV)"** to save quantification results
- Click **"Save Plot"** to save the visualization
- Click **"Show Summary"** for a table view

## For Your Tailing Problem

**Recommended Settings:**
1. Set reference band width from a clean band
2. Use **"Fixed Width (Reference)"** integration method
3. Use **"Linear"** baseline correction
4. This will:
   - Detect all peak centers automatically
   - Apply consistent width from your clean reference
   - Ignore the asymmetric tailing
   - Give reproducible, comparable results

## Output Data (CSV)

The exported CSV contains:
- **Lane**: Lane number
- **Band**: Band number within that lane
- **Area**: Integrated area (main quantification value)
- **Height**: Peak height (alternative measure)
- **Width**: Width in pixels
- **Peak_Position**: Location of peak maximum
- **Start/End**: Integration boundaries

## Tips

- **Working with multiple similar gels?** Save your lane configuration after setting up the first one, then just load it for subsequent images!
- **Quick setup for 12-lane gel:** Draw first lane, click "Add Multiple Lanes", enter 12 lanes with appropriate spacing
- **Lane configuration saved with reference width** - your complete setup is preserved
- **No reference set?** The system will auto-detect from the first peak (but manual is better!)
- **Too many/few peaks detected?** The algorithm uses a minimum distance of 20 pixels between peaks
- **Baseline issues?** Try different baseline correction methods
- **Need to see raw data?** The interactive method lets you manually verify each band

## Workflow Tips for Multiple Gels

### First Gel (Setup Phase):
1. Load image
2. Draw first lane carefully
3. Use "Add Multiple Lanes" to create all lanes
4. Fine-tune positions with arrow keys
5. Set reference band width from a clean peak
6. **Save Lane Configuration** (e.g., "gel_12lanes_config.json")
7. Analyze bands and export data

### Subsequent Gels (Fast Phase):
1. Load new image
2. **Load Lane Configuration** - done!
3. (Optional) Make small adjustments if needed
4. Analyze bands and export data

**Time saved:** Setting up 12 lanes manually (~5 min) vs loading config (~5 sec)!

## Loading Image Studio TIFFs (raw_image_studio)

This project includes support for Image Studio multi-page TIFFs (found under `raw_image_studio/`). These TIFFs are often float16 pyramid TIFFs; Pillow sometimes cannot open them directly.

Use the built-in loader which will handle these TIFFs automatically. When you `Load Image`, if a file contains multiple pages you will be prompted to choose which page to use (0 = full resolution, higher = downsampled).

If you prefer to convert many files to PNG first, use the batch converter:

```bash
PYTHONPATH=. python3 scripts/batch_convert.py path/to/raw_image_studio output_png_folder
# To export all pyramid pages per TIFF:
PYTHONPATH=. python3 scripts/batch_convert.py path/to/raw_image_studio output_png_folder --all-pages
```

This creates normalized 8-bit PNGs you can load normally.
