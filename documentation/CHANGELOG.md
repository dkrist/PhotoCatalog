# Changelog

All notable changes to the Photo Catalog App project are documented in this file.

---

## [2.0.0] — 2026-04-13

### Added — Windows Installer / Distribution

- **`packaging/PhotoCatalog.spec`** — PyInstaller `--onedir` recipe that
  bundles the PyQt6 GUI, `Images/` folder, and app icon. Trims ~40–60 MB
  of unused Qt modules (Qt3D, WebEngine, Multimedia, etc.) via `excludes`.
- **`packaging/PhotoCatalog.iss`** — Inno Setup 6 script that wraps the
  PyInstaller output into a single-file setup installer. Installs into
  `Program Files\PhotoCatalog`, creates a Start Menu shortcut, and
  offers an optional desktop icon. Stable `AppId` GUID so upgrades
  replace the existing install cleanly.
- **`packaging/build.ps1`** — one-shot PowerShell orchestration script
  that runs PyInstaller then Inno Setup. Supports `-Clean` (nuke
  `build\`, `dist\`, `release\` first) and `-SkipInstaller` (for fast
  iteration without re-packaging).
- **`documentation/RELEASING.md`** — end-to-end release guide covering
  toolchain setup, build command, smoke-test checklist, version
  bumping, GitHub Releases publishing, the Windows SmartScreen warning
  explanation, and a troubleshooting section.
- **`Images/photocatalog.ico`** — multi-resolution app icon
  (16/24/32/48/64/128/256 px) used by both the PyInstaller `.exe` and
  the Inno Setup installer.
- Final artifact: `release\PhotoCatalog-Setup-<version>.exe`, ready to
  attach to a GitHub Release.

### Added — Desktop UI (PyQt6)

- **`scripts/gui_main.py`** — new PyQt6 desktop UI matching the project
  wireframe (`Images/PhotoCatalog UI Wireframe.png`). Features:
  - Header with camera icon, title, version, and "Built with Claude" badge
    using the PNGs in `Images/`.
  - "Select Photo Folder" and "Save Report to Folder" inputs with Browse
    buttons that open modal folder-select dialogs.
  - Green **Start Cataloging Process** button that disables during a run.
  - Live **Progress** bar with a `current/total` counter formatted as
    `nnn,nnn/nnn,nnn`.
  - **Open Catalog Report** button (enabled after a successful run).
  - **Process Log Messages** panel that tails the run in real time, plus
    an **Open Process Log** button to open the full log file.
- **`scripts/catalog_pipeline.py`** — extracted reusable `run_catalog()`
  function used by both the CLI (`run_catalog.py`) and the new GUI, with
  support for progress callbacks, log callbacks, and cooperative
  cancellation via `threading.Event`.
- **`scripts/run_gui.py`** — launcher script for the UI.
- Folder inputs pre-populate from `default_scan_folder` and
  `save_report_to` settings; both are saved back after each run.
- Pipeline runs on a `QThread` with `pyqtSignal` updates so the UI stays
  responsive. Closing the window mid-run prompts to cancel cleanly.
- `PyQt6>=6.6.0` added to `requirements.txt`.

### Added — Application Settings Management

- **`scripts/settings.py`** — New user-settings module backed by a JSON file
  at `%APPDATA%\PhotoCatalog\config.json` (cross-platform via `platformdirs`
  when available, with `%APPDATA%` / `~/.config` fallbacks).
- **Settings supported:**
  - `save_report_to` — folder where generated Excel reports are written
    (default: `~/Documents/PhotoCatalog/Reports`).
  - `log_file_folder` — folder where application log files are written
    (default: `~/Documents/PhotoCatalog/Logs`).
  - `default_scan_folder` — last-used photo folder, used to seed the GUI picker.
  - `enable_face_recognition` — default toggle (overridden by `--no-faces`).
  - `log_level` — logging verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`).
  - `recent_folders` — last 10 scanned folders.
- **File logging** added to `run_catalog.py` — every run now writes a
  timestamped log file to `log_file_folder` in addition to console output.
- **`--show-settings` flag** added to `run_catalog.py` for printing the
  current config file path and values.
- **`platformdirs`** added to `requirements.txt`.

### Changed

- `run_catalog.py` now resolves the report output folder from
  `save_report_to` instead of the hardcoded `output/` path.
- GUI folder picker now seeds its initial directory from the user's last
  scanned folder.

---

## [0.1.0] — 2026-03-03

### Initial Release — Core MVP

**Summary:** Built and tested the complete photo metadata extraction pipeline from scratch. Scanned 542 iPhone photos, extracted 57 columns of metadata, and generated a formatted Excel workbook with catalog and summary sheets.

### Added

#### Project Setup
- Created project folder structure: `inbox/`, `scripts/`, `documentation/`, `output/`, `tests/`
- Created `requirements.txt` with openpyxl and Pillow dependencies
- Created `documentation/USAGE.md` with quick-start guide and folder structure reference
- Created `documentation/Photo_Catalog_App_Project.md` with full project specification

#### Core Script (`scripts/photo_catalog.py`)
- Folder scanner that filters for 12 supported image formats (JPG, JPEG, TIFF, PNG, HEIF, HEIC, WebP, CR2, CR3, NEF, ARW, DNG, ORF, RW2)
- EXIF metadata extraction via Pillow with human-readable value mapping for:
  - Exposure programs (8 modes)
  - Metering modes (7 types)
  - Flash modes (10 states)
  - Orientation (8 values)
  - Scene capture types (4 types)
  - White balance modes (2 types)
  - Exposure modes (3 types)
  - Sensing methods (7 types)
  - Color spaces (2 values)
- GPS coordinate extraction with DMS-to-decimal conversion (6 decimal places)
- GPS altitude, speed, image direction, and date stamp extraction
- XMP metadata extraction via raw byte scanning + xml.etree parsing
- XMP face region detection (Apple mwg-rs:Regions with face count)
- Dynamic XMP namespace discovery (captures non-standard fields automatically)
- Exposure time formatting (decimal → fractional, e.g., 0.0002 → "1/4975")
- Lens specification formatting (e.g., "2.2-15.7mm f/1.78-2.8")
- File metadata: name, path, size (human-readable + bytes), dimensions

#### Excel Output (`openpyxl`)
- **Catalog sheet:** One row per photo with all metadata columns
  - Blue header row with white bold text (frozen, auto-filtered)
  - Alternating row colors (white/light gray)
  - Auto-fit column widths (sampled from first 50 rows)
  - Thin border separators
- **Summary sheet:** Aggregate statistics including:
  - Folder name and generation timestamp
  - Total photo count
  - Date range (earliest, latest, span in days)
  - Camera models with photo counts
  - Lens models with photo counts
  - ISO range (min, max, average)
  - Aperture range
  - Focal length range (35mm equivalent)
  - GPS coverage (count and percentage)
  - Face detection stats (photos with faces, total faces detected)
- Output file naming: `PhotoCatalog_[FolderName]_[YYYY-MM-DD].xlsx`

#### Runner Script (`scripts/run_catalog.py`)
- Quick-run wrapper that catalogs the `inbox/` folder by default
- Accepts any folder path as a command-line argument
- Writes output to the `output/` directory automatically

#### Configuration (`scripts/config.py`)
- Centralized constants: supported extensions, column ordering, EXIF tag mappings
- XMP namespace registry (13 namespaces)
- Separated from main script for maintainability

### Technical Decisions
- **Pure Python approach:** Used Pillow + xml.etree instead of ExifTool to avoid system-level dependencies. ExifTool remains a planned upgrade path for deeper metadata coverage.
- **Dynamic columns:** Column list is derived from the union of all fields found across all photos (not hardcoded), ensuring no metadata is silently dropped.
- **Preferred column ordering:** Known fields appear in a logical order (file info → camera → dates → exposure → GPS → XMP); unknown fields are appended alphabetically.

### Test Results
- Processed 542 photos (iPhone 16 Pro Max + iPhone 15 Pro Max)
- Extracted 57 unique metadata columns
- Full run completed successfully with no errors
