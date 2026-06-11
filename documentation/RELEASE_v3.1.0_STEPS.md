# PhotoCatalog v3.1.0 — Release Steps

Follow these steps on your Windows PC to build, test, and publish the v3.1.0 release.

---

## Prerequisites (one-time, already done for v3.0.0)

- Python 3.14 with dependencies: `pip install -r requirements.txt`
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6 installed from https://jrsoftware.org/isinfo.php
- Git configured and authenticated with GitHub

---

## Step 1: Final Test Run

Before building, launch the app from source one more time to verify everything:

```powershell
cd C:\GitHub\PhotoCatalog
python scripts\gui_main.py
```

Quick checks:
- [ ] Header shows "V3.1 - 6/11/2026"
- [ ] Help menu > Quick Reference opens and shows V3.1
- [ ] Help menu > Full Documentation opens help.html in browser
- [ ] Rename template button palette works (click buttons to build template)
- [ ] Test Rename String runs and shows checkmark
- [ ] Build Renames is disabled until Test passes
- [ ] Elapsed timer appears during operations
- [ ] Tooltips appear on all buttons
- [ ] Close window while a process is running — confirmation dialog appears
- [ ] Keyboard shortcuts work (Ctrl+P, Ctrl+T, etc.)

---

## Step 2: Build the Installer

Run the build script from the project root:

```powershell
cd C:\GitHub\PhotoCatalog
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Clean
```

The `-Clean` flag deletes old `build\`, `dist\`, and `release\` folders first.

This runs three phases:
1. Verifies PyInstaller is installed
2. Builds `dist\PhotoCatalog\PhotoCatalog.exe` (plus DLLs and resources)
3. Runs Inno Setup to create `release\PhotoCatalog-Setup-3.1.0.exe`

Expected output at the end:
```
===================================================
  Installer: C:\GitHub\PhotoCatalog\release\PhotoCatalog-Setup-3.1.0.exe  (XX MB)
===================================================
```

---

## Step 3: Smoke-Test the Built Executable

Test the PyInstaller output directly first:

```powershell
.\dist\PhotoCatalog\PhotoCatalog.exe
```

- [ ] App launches without errors
- [ ] Header shows V3.1, camera icon is white, no border boxes
- [ ] Help > Full Documentation opens (this was broken in v3.0.0 — now fixed)
- [ ] SVG icons render correctly (camera icon in header, checkmarks on buttons)
- [ ] Run a quick pre-scan + catalog on a small test folder

---

## Step 4: Smoke-Test the Installer

1. Double-click `release\PhotoCatalog-Setup-3.1.0.exe`
2. Follow the install wizard
3. Verify:
   - [ ] Start Menu shortcut appears under "PhotoCatalog"
   - [ ] App launches from the shortcut
   - [ ] Version shows V3.1 in the header
   - [ ] Help > Full Documentation works (this was the packaging fix)
   - [ ] Quick test: scan a small folder, test rename, copy to destination
4. Uninstall from Settings > Apps > PhotoCatalog — confirm clean removal

---

## Step 5: Commit All Changes and Tag

```powershell
cd C:\GitHub\PhotoCatalog

# See what's changed
git status
git diff --stat

# Stage all source changes (NOT the build artifacts)
git add scripts\gui_main.py
git add scripts\rename_engine.py
git add packaging\PhotoCatalog.spec
git add packaging\PhotoCatalog.iss
git add documentation\CHANGELOG.md
git add documentation\RELEASING.md
git add documentation\help.html
git add documentation\WORKFLOW.md
git add Images\camera-icon-white.svg
git add Images\checkmark-white.svg
git add README.md

# Commit
git commit -m "Release v3.1.0 — polished UI, rename template palette, workflow gating"

# Tag
git tag v3.1.0 -m "PhotoCatalog v3.1.0"

# Push commit and tag
git push origin main
git push origin v3.1.0
```

---

## Step 6: Create GitHub Release

1. Go to https://github.com/dkrist/PhotoCatalog/releases
2. Click **"Draft a new release"**
3. Choose tag: **v3.1.0**
4. Title: **PhotoCatalog v3.1.0**
5. Paste the release notes below into the body
6. Drag and drop `release\PhotoCatalog-Setup-3.1.0.exe` into the "Attach binaries" area
7. Click **"Publish release"**

---

## Release Notes (copy-paste into GitHub)

```markdown
## Install (Windows 10 / 11)

1. Download **PhotoCatalog-Setup-3.1.0.exe** from the Assets below.
2. Double-click it. If Windows SmartScreen warns you, click
   "More info" → "Run anyway" — this is normal for apps without a
   code signing certificate.
3. Follow the installer prompts. The app will appear in your Start Menu.

## What's New in v3.1.0

**Polished UI, guided rename workflow, and quality-of-life improvements.**

### Rename template builder
- **Clickable variable buttons** replace the free-text variable list. Click pill-shaped buttons (YYYY, MM, DD, Make, Name, separators) to build the template visually. You can still type freely in the text box.
- **File extension auto-appended** — the engine now adds the original extension automatically, eliminating the most common template mistake.

### Workflow safeguards
- **Test-before-Build gating** — Build Renames stays disabled until Test Rename passes on the current template, with a visible warning label.
- **Checkmarks on every action button** show which steps are complete. They reset automatically when inputs change.
- **Copy to Destination confirmation** now notes whether renames have been built and tested.
- **Close confirmation** for all running background processes.
- **Source = Destination guard** warns immediately if both folders are the same.

### Responsiveness
- **Elapsed time badge** next to the progress bar during Pre-Scan, Cataloging, Test Rename, and Build Renames.
- **Keyboard shortcuts:** Ctrl+P (Pre-Scan), Ctrl+Enter (Catalog), Ctrl+T (Test Rename), Ctrl+D (Detect Dupes), Ctrl+Z (Undo).
- **Non-keepers folder label** below Destination Folder shows the full DupeHolding path.

### UI polish
- Rounded button corners, white SVG camera icon on the blue header, dark-bordered template text box, HTML tooltips on all buttons, thick section separators, renamed "Progress & Activity Log" panel.

### Packaging fixes
- Help file now bundled in the installer (was missing in v3.0.0).
- SVG icon support included in the build.

---

Full changelog: https://github.com/dkrist/PhotoCatalog/blob/main/documentation/CHANGELOG.md
```

---

## Step 7: Share

Share the release URL with testers:

```
https://github.com/dkrist/PhotoCatalog/releases/latest
```

---

## Troubleshooting

**Build fails with "ModuleNotFoundError: No module named 'PyQt6.QtSvg'"**
This shouldn't happen (we removed QtSvg from excludes), but if it does, run `pip install PyQt6` to ensure the full package is installed.

**Help file doesn't open in the installed version**
Verify that `dist\PhotoCatalog\_internal\documentation\help.html` exists after the PyInstaller step. If not, check that the `datas` line in `PhotoCatalog.spec` includes the documentation entry.

**SVG icons don't render (blank squares)**
Check that `dist\PhotoCatalog\_internal\PyQt6\Qt6\plugins\iconengines\qsvgicon.dll` exists. If not, PyQt6.QtSvg may still be in the excludes list.

**SmartScreen warning on first launch**
Normal for unsigned executables. Users click "More info" → "Run anyway." The release notes include this explanation.
