# Building an Executable

## Quick Method (Recommended)

### 1. Install PyInstaller
```bash
pip3 install pyinstaller
```

### 2. Build the Executable
```bash
cd ~/WB_quantifier
pyinstaller --name="WesternBlotQuantifier" --windowed --onefile wb_quantifier_advanced.py
```

### 3. Find Your Executable
- **Location**: `dist/WesternBlotQuantifier` (or `dist/WesternBlotQuantifier.app` on macOS)
- **Size**: ~80-150 MB (includes Python + all libraries)
- **Portable**: Can be copied to any Mac without Python installed

### 4. Run It
```bash
./dist/WesternBlotQuantifier
```
Or just double-click `WesternBlotQuantifier.app` in Finder!

---

## Advanced Build (With Icon and Optimizations)

### Create an Icon (Optional)
If you want a custom icon:
1. Create a 512x512 PNG image
2. Convert to .icns on macOS:
```bash
# Use online converter or:
sips -s format icns icon.png --out icon.icns
```

### Build with Options
```bash
pyinstaller \
  --name="WesternBlotQuantifier" \
  --windowed \
  --onefile \
  --icon=icon.icns \
  --add-data="README_ADVANCED.md:." \
  --hidden-import="PIL._tkinter_finder" \
  --osx-bundle-identifier="com.yourlab.wbquantifier" \
  wb_quantifier_advanced.py
```

**Options explained:**
- `--windowed`: No terminal window (GUI only)
- `--onefile`: Single executable file
- `--icon`: Custom icon
- `--add-data`: Include README in bundle
- `--hidden-import`: Ensure PIL/tkinter works

---

## Distribution Options

### Option 1: Single Executable (Easiest)
```bash
pyinstaller --windowed --onefile wb_quantifier_advanced.py
```
**Pros**: Single file, easy to share  
**Cons**: Slower startup (unpacks temp files)  
**Size**: ~100 MB

### Option 2: Directory Bundle (Faster)
```bash
pyinstaller --windowed wb_quantifier_advanced.py
```
**Pros**: Faster startup  
**Cons**: Multiple files in folder  
**Size**: ~100 MB total

### Option 3: macOS .app Bundle (Professional)
```bash
pyinstaller --windowed --onefile --osx-bundle-identifier="com.lab.wbquantifier" wb_quantifier_advanced.py
```
**Pros**: Native macOS app, can add to Applications  
**Cons**: macOS only  
**Size**: ~100 MB

---

## Creating a DMG Installer (macOS)

For professional distribution on Mac:

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "Western Blot Quantifier" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --app-drop-link 600 185 \
  "WesternBlotQuantifier.dmg" \
  "dist/WesternBlotQuantifier.app"
```

Users can then:
1. Download the .dmg
2. Drag to Applications folder
3. Double-click to run!

---

## Cross-Platform Building

### For Windows (from Mac)
Not directly possible. Need to build on Windows:
```bash
pip install pyinstaller
pyinstaller --windowed --onefile wb_quantifier_advanced.py
# Creates: dist/WesternBlotQuantifier.exe
```

### For Linux (from Mac)
Not directly possible. Need to build on Linux:
```bash
pip install pyinstaller
pyinstaller --windowed --onefile wb_quantifier_advanced.py
# Creates: dist/WesternBlotQuantifier
```

**Note**: Each platform needs its own build.

---

## Troubleshooting

### "Module not found" errors
Add hidden imports:
```bash
pyinstaller --hidden-import=scipy.special._ufuncs_cxx --windowed --onefile wb_quantifier_advanced.py
```

### Large file size
This is normal. The executable includes:
- Python interpreter
- NumPy, Matplotlib, SciPy, PIL
- All dependencies

To reduce size slightly:
```bash
# Use UPX compression (optional)
brew install upx
pyinstaller --upx-dir=/usr/local/bin --windowed --onefile wb_quantifier_advanced.py
```

### macOS Security Warning
First time running, macOS might block it:
1. Right-click the app
2. Choose "Open"
3. Click "Open" in the dialog

Or code-sign it (requires Apple Developer account):
```bash
codesign --force --deep --sign - dist/WesternBlotQuantifier.app
```

---

## Simple Build Script

I've created `build_executable.sh` for you. Just run:

```bash
chmod +x build_executable.sh
./build_executable.sh
```

---

## Sharing with Others

### Method 1: Direct Share
```bash
zip -r WesternBlotQuantifier.zip dist/WesternBlotQuantifier.app
# Send the .zip file
```

### Method 2: GitHub Release
1. Push code to GitHub
2. Create a release
3. Attach the .app or .zip as an asset
4. Users download and run

### Method 3: Lab Server
Place the .app on a shared network drive for lab members

---

## Estimated Sizes

- **macOS .app**: ~90-120 MB
- **Windows .exe**: ~70-100 MB  
- **Linux binary**: ~80-110 MB

The size is worth it for:
- ✅ No Python installation needed
- ✅ No dependency issues
- ✅ Works on any computer
- ✅ Professional appearance
- ✅ Easy for non-programmers to use

---

## Quick Start (TL;DR)

```bash
# Install PyInstaller
pip3 install pyinstaller

# Build
cd ~/WB_quantifier
pyinstaller --windowed --onefile --name="WesternBlotQuantifier" wb_quantifier_advanced.py

# Run
./dist/WesternBlotQuantifier
```

**Done!** You now have a standalone app.
