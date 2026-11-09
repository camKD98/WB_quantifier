#!/bin/bash
# Build script for Western Blot Quantifier

echo "Building Western Blot Quantifier executable..."

# Install PyInstaller if not already installed
pip3 install pyinstaller

# Build the executable
pyinstaller --name="WesternBlotQuantifier" \
            --windowed \
            --onefile \
            --icon=icon.icns \
            --add-data="README_ADVANCED.md:." \
            --hidden-import="PIL._tkinter_finder" \
            wb_quantifier_advanced.py

echo ""
echo "Build complete!"
echo "Executable location: dist/WesternBlotQuantifier"
echo ""
echo "To create a .app bundle on macOS:"
echo "The executable is already in dist/WesternBlotQuantifier.app"
