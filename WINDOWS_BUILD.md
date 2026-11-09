# Cross-Platform Build Guide

## Building Windows .exe from macOS

You have several options:

### Option 1: GitHub Actions (RECOMMENDED - Easiest)

**Setup (One-time):**
1. Push your code to GitHub
2. The `.github/workflows/build.yml` file is already included
3. Create a release tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

**Result:**
- GitHub automatically builds for macOS, Windows, AND Linux
- Downloads available as release assets
- No Windows machine needed!

**To use:**
```bash
# Initialize git (if not already done)
cd ~/WB_quantifier
git init
git add .
git commit -m "Initial commit"

# Create GitHub repo and push
# (Follow GitHub's instructions to create repo)
git remote add origin https://github.com/YOUR_USERNAME/WB_quantifier.git
git push -u origin main

# Create a release
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will automatically build:
- `WesternBlotQuantifier-macOS.zip` (contains .app)
- `WesternBlotQuantifier-Windows.zip` (contains .exe)
- `WesternBlotQuantifier-Linux.zip` (contains Linux binary)

---

### Option 2: Windows Virtual Machine

**Using VirtualBox or Parallels:**
1. Install Windows 10/11 in a VM
2. Install Python 3.12 in Windows
3. Copy your project to Windows
4. Run:
   ```bash
   pip install -r requirements_advanced.txt
   pip install pyinstaller
   pyinstaller --windowed --onefile wb_quantifier_advanced.py
   ```

**Pros:** Native build, full control  
**Cons:** Requires VM setup, takes disk space

---

### Option 3: Wine (Windows Emulation on macOS)

**Not recommended** - Wine + PyInstaller is unreliable for GUI apps

---

### Option 4: Use a Cloud Windows Instance

**AWS/Azure/DigitalOcean:**
1. Spin up a Windows Server instance
2. Install Python and dependencies
3. Build the executable
4. Download and terminate instance

**Pros:** Pay-per-use, no VM on your Mac  
**Cons:** Costs a few dollars per build

---

### Option 5: Ask a Windows User

**Simplest for occasional builds:**
1. Share your Python files
2. They run the build command
3. Send you back the .exe

---

## Recommended: GitHub Actions

This is by far the **easiest and most professional** approach:

### Benefits:
✅ Free (GitHub Actions is free for public repos)  
✅ Automatic builds for all platforms  
✅ No Windows/Linux machine needed  
✅ Professional release workflow  
✅ Build history and versioning  
✅ Easy to share with collaborators  

### Quick Setup:

```bash
# 1. Create GitHub repo (on github.com)
# Click "New Repository" → "WB_quantifier"

# 2. Push your code
cd ~/WB_quantifier
git init
git add .
git commit -m "Western Blot Quantifier v1.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/WB_quantifier.git
git push -u origin main

# 3. Create a release
git tag v1.0.0
git push origin v1.0.0

# 4. Wait ~10 minutes
# GitHub Actions will build all three versions automatically
# Download from: https://github.com/YOUR_USERNAME/WB_quantifier/releases
```

---

## Manual Trigger (Without Release Tag)

You can also manually trigger builds:

1. Go to GitHub repo → Actions tab
2. Select "Build Executables" workflow
3. Click "Run workflow"
4. Download artifacts from the workflow run

---

## Testing the Windows .exe

If you don't have Windows, you can:

1. **Use Windows in Browser** (free for testing):
   - https://windows365.microsoft.com (trial)
   - https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/

2. **Ask lab members** to test it

3. **Use Wine** (just for testing, not for building):
   ```bash
   brew install --cask wine-stable
   wine dist/WesternBlotQuantifier.exe
   ```

---

## What You'll Get

After GitHub Actions completes, you'll have:

```
WesternBlotQuantifier-macOS.zip
  └── WesternBlotQuantifier.app (for Mac)

WesternBlotQuantifier-Windows.zip
  └── WesternBlotQuantifier.exe (for Windows)

WesternBlotQuantifier-Linux.zip
  └── WesternBlotQuantifier (for Linux)
```

All ready to distribute to users!

---

## File Sizes (Approximate)

- macOS: ~100 MB
- Windows: ~80 MB
- Linux: ~90 MB

Each includes Python + all dependencies, so they're standalone.

---

## I Recommend:

**Use GitHub Actions** - it's free, automated, and builds for all platforms without needing Windows/Linux machines!
