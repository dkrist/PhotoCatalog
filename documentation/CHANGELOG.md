# Changelog

All notable changes to the Photo Catalog App project are documented in this file.

---

## [3.0.0] — 2026-04-15

### Headline — reorganize a messy photo drive into a clean destination

v3 extends PhotoCatalog from "scan and rename in place" to "scan,
detect duplicates, and copy into a date-organized destination." The
full rationale and decision log lives in
`documentation/v3_design_notes.md`; the implementation below mirrors
that document.

### Added — Destination folder + checkbox-driven folder layout

- **New required Destination Folder picker** on the main window, sits
  between *Save Report to Folder* and the action buttons.
- **Folder Layout checkboxes** replace what would otherwise have been
  a second free-text template. Three nested level pickers — *Year*,
  *Month*, *Day* — each with a format radio group (e.g. `YYYY`,
  `MM - MonthName`, `YYYY-MM-DD`). The app composes the path in
  Year → Month → Day order and renders a live **Destination preview**
  label so the user can see exactly what path one of their photos will
  land at.
- **`File_DestFolder`** and **`File_DestPath`** columns added to the
  Catalog sheet. `File_DestFolder` is the rendered path under the
  destination root; `File_DestPath` is the full copy target including
  the rename filename.
- Files whose date sources (`DateTimeOriginal` and `File_Date`) are
  both missing land in a literal `Unknown_Date` folder with a
  `[WARN]` entry in `File_Concern`.

### Added — Duplicate detection

- **New Dupe Detection mode combo box** on the main window with three
  choices: *None*, *Filename + Size* (match on lowercased basename +
  `File_SizeBytes`), and *MD5 Hash* (full-bytes match, slower).
  Selecting Hash prompts the user to confirm the longer run time.
- **`File_Hash` column** (MD5 hex string, 32 chars). Populated only when
  Hash mode is selected; blank otherwise.
- **`File_DupeGroup`** (integer) groups duplicates together so the
  Excel user can sort/filter by group. **`File_DupeKeep`** (`TRUE` /
  `FALSE`) marks exactly one row per group as the keeper (earliest
  `File_Date` wins; ties broken by shortest source path).
- **Distinct pale-orange highlight** (`FFFFD59B`) on the `File_Name`
  cell when a row belongs to any duplicate group, so duplicates read
  at a glance without needing to sort the workbook.
- The user may edit `File_DupeKeep` before running Move or Delete;
  the downstream engines respect the workbook's current values.

### Added — Copy engine with sidecar handling

- **New *Copy to Destination* button** runs a background pass that
  reads `File_DestPath` for every row and copies the source file into
  place. `File_Status` transitions from blank to `Copied` on success.
- **Sidecar files follow the primary.** When copying `IMG_0001.NEF`,
  any same-stem companions in the same source folder
  (`IMG_0001.JPG`, `IMG_0001.xmp`, `IMG_0001.aae`, `IMG_0001.thm`,
  `IMG_0001.dop`) are copied to the same destination folder under the
  same stem, so edit histories and raw+jpg pairs stay intact.
- **Automatic destination collision suffixing.** If a file already
  exists at the target path, the copy writes to `..._2`, `..._3`, etc.,
  and appends a `[WARN]` entry in `File_Concern` noting the renamed
  destination path.

### Added — Rollback journal and Undo

- Every destructive-ish operation (Copy, Move-non-keepers,
  Delete-non-keepers) writes a **`_rollback_<YYYYMMDD_HHMMSS>.jsonl`**
  file in the destination folder, one line per file touched.
- **New *Undo Last Operation* button** reads the newest journal in
  reverse and reverses each entry — deletes copied files, moves files
  back, etc. Unrecoverable entries (e.g. a deleted source whose
  backup doesn't exist) are listed in the log so the user can recover
  manually from backup.

### Added — Non-keeper disposal

- **Move non-keepers...** button moves rows where `File_DupeKeep =
  FALSE` from their source location to a user-chosen holding folder,
  preserving their relative path so the user can review and discard at
  leisure.
- **Delete non-keepers from source** button deletes rows where
  `File_DupeKeep = FALSE` from the source drive, with a strong
  two-step confirmation and a complete rollback journal.
- Both operations update `File_Status` to `DupeMoved` or
  `DupeDeleted`.

### Added — Empty source folder cleanup

- After a Move or Delete non-keepers pass, a final pass walks the
  source tree and lists any folders that are now empty in
  `_source_cleanup_candidates.log`. A confirmation dialog ("Remove N
  now-empty source folders?") gates the actual removal, and the
  removals are added to the rollback journal.

### Added — MD5 hash column (opt-in)

- **`File_Hash`** — 32-character lowercase MD5 hex string. Computed
  per file with a streaming 1 MB-buffer read so large RAW files don't
  balloon memory. Populated only when the Hash dupe mode is selected
  for the run. A non-cryptographic algorithm is deliberately chosen:
  this is for "are these the same bytes," not for signing.

### Added — Full UI-state persistence

- `settings.py` gains v3 keys so the entire main window state round-trips
  through a restart: `destination_folder`, `rename_template`,
  `folder_level_year` / `folder_format_year` (and matching month/day),
  `dupe_mode`, and `operation_default`. Opening the app tomorrow fills
  every field with yesterday's values.
- Settings still live at `%APPDATA%\PhotoCatalog\settings.json` on
  Windows (same file v2.x used); unknown future keys survive a
  save-load round-trip.

### Changed — Column order

- New `File_` columns insert into COLUMN_ORDER between `File_Date`
  and `File_Concern` so the expanded `File_` block still groups at
  the left edge of the sheet:

  `File_Name`, `File_Extension`, `File_RenameName`, `File_Size`,
  `File_SizeBytes`, `File_Date`, `File_Hash`, `File_DupeGroup`,
  `File_DupeKeep`, `File_DestFolder`, `File_DestPath`,
  `File_Status`, `File_Concern`, `File_Path`.

### Changed — Pipeline orchestration

- `catalog_pipeline.run_catalog` now accepts `dupe_mode`,
  `folder_config`, and `destination_folder` parameters and attaches
  them to the catalog run. Callers that omit these fall back to v2.1.x
  behavior (dupe detection off, no destination composition, rename
  in-place only).

### Engineering notes

- New modules: `duplicate_detector.py`, `folder_composer.py`,
  `copy_engine.py`, `rollback.py`.
- v2.1.x workbooks remain readable; new columns are appended on the
  right when they're missing on load, matching the pattern introduced
  in v2.1.1's `_ensure_column`.

---

## [2.1.1] — 2026-04-14

### Added — Template viability check (CR #2)

- **Pre-flight validation on the rename template itself.** Both *Test
  Rename String* and *Build Renames for all Photos* now run a
  pattern-based check on the template before any rendering starts so
  the user doesn't discover the template was broken only after watching
  thousands of rows render into garbage.
- **Errors (block execution):**
  - Template does not produce a file extension (no `%File_Extension%`
    token and doesn't end with a literal extension like `.jpg`,
    `.heic`, `.cr2`, etc.).
  - Template has no `%Variable%` tokens at all, which would rename
    every photo to the same literal string.
  - Template is empty or whitespace-only.
  - Template contains unknown tokens (previously surfaced inconsistently
    between Test and Build — now rolled into the unified check).
- **Warnings (confirm to proceed):**
  - Template does not include `%File_Name%`. Photos taken on the same
    date by the same camera would collide en masse. Still valid if
    intentional; the per-row preflight will still flag the actual
    collisions with `[ERROR]` markers in `File_Concern`.
  - Template contains path separators (`/` or `\\`). The rename engine
    does not create subfolders; separators are stripped from the
    rendered filename.
- **UI flow:** when the template has errors, a single
  `QMessageBox.critical` lists every error *and every warning* in one
  pass (plus the valid-variable cheat sheet) so the user addresses
  everything in one fix-test cycle instead of discovering problems one
  at a time. Warning-only templates show a `QMessageBox.question` with
  "Proceed anyway / Cancel." Clean templates run exactly as before.
- **Engine-level safety net.** `check_template_viability()` is also
  called inside `build_renames()` and `test_template()` themselves, so
  any future caller that bypasses the GUI still gets the same
  protection — errors raise `ValueError`, warnings stream to the log.
- New module entry point: `rename_engine.check_template_viability`.

### Changed — Column naming & grouping (CR #1)

- **`File_` prefix applied to all app-generated / filesystem-sourced columns.**
  `FileName`, `FileExtension`, `RenameFileName`, `FilePath`, `FileSize`,
  and `FileSizeBytes` became `File_Name`, `File_Extension`,
  `File_RenameName`, `File_Path`, `File_Size`, and `File_SizeBytes`
  respectively. The prefix visually separates catalog-owned columns
  from EXIF/XMP camera-sourced fields and aligns the column names with
  the existing underscored rename-variable style (`%File_Name%`,
  `%File_Extension%`, `%Camera_Make%`). All `File_` columns now group
  together on the left edge of the Catalog sheet.

### Added — `File_Date` column (CR #1)

- **New `File_Date` column** captures the filesystem Modified timestamp
  (`os.stat().st_mtime`) for every cataloged image, positioned inside
  the `File_` group. Stored as a proper Excel datetime so it sorts and
  filters alongside `DateTimeOriginal`.
- **Rename-engine date fallback.** The `%Date_YY%` / `%Date_YYYY%` /
  `%Date_MM%` / `%Date_DD%` variables now fall back to `File_Date`
  when `DateTimeOriginal` is blank. Rows are skipped only when *both*
  dates are missing. Each fallback row gets an `[INFO]` marker in
  `File_Concern`. Catalogs of scanned documents, Lightroom exports,
  and copied-off-camera files that previously rendered blank names
  now produce usable renames.

### Added — `File_Concern` column with severity tiers (CR #1)

- **New `File_Concern` column** (positioned just before `File_Path`)
  promotes previously-silent issues to first-class data:
  - `[INFO]` — benign notices such as fallback-date usage.
  - `[WARN]` — correctable conditions such as sanitized illegal EXIF
    characters or `ZeroDivisionError` skips on rational fields.
  - `[ERROR]` — conditions that block the future on-disk rename/move:
    rename collisions within the same target folder, renders exceeding
    Windows' 255-character filename limit, empty renders, and
    `os.stat()` failures on unreadable files.
- **Color-coded cells.** `File_Concern` cells are filled pale yellow
  (`FFFFE699`) when only `[INFO]` / `[WARN]` markers are present and
  pale red (`FFFFC7CE`) when any `[ERROR]` marker is present; color is
  driven by the highest severity, and multiple messages within a row
  are joined with `; `.
- **End-of-run log summary.** The Process Log now reports one line per
  run summarizing the marker tally, e.g.
  `File_Concern markers: [INFO] 142, [WARN] 17, [ERROR] 3 across 159 row(s)`,
  so the user sees the gist without scrolling the workbook.

### Added — Rename preflight validation (CR #1)

- **Build Renames now validates before writing.** The rename pass
  runs in two stages: render all rows, then check every rendered name
  for emptiness, over-length, and collisions within the same parent
  folder. Failing rows get `[ERROR]` concerns appended and
  `File_RenameName` left blank so the future on-disk move pass skips
  them cleanly. Passing rows write the rendered name as before.
- **Rename-run log summary** extended with counts for
  `File_Date` fallbacks and `[ERROR]` rows, in addition to the existing
  renamed / skipped totals.
- **Concern preservation.** Appending rename-time concerns to an
  existing `File_Concern` cell no longer stomps the extract-time
  concerns written during the catalog phase. Duplicate messages are
  suppressed so repeated Build Renames passes don't accumulate noise.
- **Backward compatibility.** `test_template` and `build_renames`
  transparently read workbooks written by v2.1.0 (which use the old
  un-prefixed header names) so earlier catalogs can be re-renamed
  without re-scanning.

---

## [2.1.0] — 2026-04-14

### Fixed

- **`IllegalCharacterError` on quirky camera EXIF padding.** Some older
  cameras (e.g. Canon PowerShot SD1000) store the `Model` tag as
  `"Canon PowerShot SD1000"` followed by NUL byte padding. openpyxl
  refuses to write strings containing ASCII control characters and
  raises `IllegalCharacterError` during `wb.save()`, which aborts the
  whole workbook write at the very end of a long run. Added
  `_sanitize_cell_value()` that strips characters in the
  `\x00-\x08 / \x0b-\x0c / \x0e-\x1f` ranges from any string before it
  reaches an Excel cell. Non-string values (datetimes, ints, floats)
  pass through untouched so date-formatting still works.
- **`ZeroDivisionError` on scanner-produced JPEGs.** Scanned documents
  (passports, receipts, flatbed scans) often have partial EXIF with
  `ExposureTime = 0` or rational fields whose denominator is `0`, which
  crashed `format_exposure_time()` and every `float(value)` call on
  Pillow `IFDRational` objects — aborting the whole run mid-catalog.
  Added a `_safe_float()` helper that swallows `ZeroDivisionError` (in
  addition to `TypeError`/`ValueError`) and routed all numeric EXIF
  extraction (`FNumber`, `ISO`, `ShutterSpeedValue`, `ApertureValue`,
  `BrightnessValue`, `ExposureBiasValue`, `FocalLength`,
  `FocalLengthIn35mmFilm`, `XResolution`, `YResolution`) through it.
  Also caught `ZeroDivisionError` in `format_exposure_time`,
  `format_lens_spec`, and the GPS altitude/speed/direction parsers.
  Malformed fields now leave the column blank for that one file
  instead of failing the catalog.
- **Whole-drive / multi-subfolder scans now work.** `scan_folder()` was
  using `os.listdir()` and only ever returned files in the top level of
  the selected folder, so pointing it at a drive root or any
  folder-of-folders produced *"No supported image files found."* It now
  uses `os.walk()` and recurses through every subfolder. Windows system
  folders (`$RECYCLE.BIN`, `System Volume Information`), hidden/dot
  folders, and common dev folders (`.git`, `__pycache__`, `node_modules`,
  `venv`) are pruned from the walk to keep counts meaningful.

### Added

- **`FileExtension` column.** New column sits immediately right of
  `FileName` in the Catalog sheet, populated with the lowercase
  extension-with-dot (e.g. `.jpg`, `.heic`, `.cr2`). Normalization means
  mixed-case on-disk names (`IMG_6596.JPG` vs `img_6596.jpg`) collapse
  to a single value so sorting, filtering, and pivot-by-type all work
  cleanly.

- **`RenameFileName` column + rename template engine.** New column sits
  immediately right of `FileExtension` in the Catalog sheet (blank at
  catalog time) and is populated by the new rename tooling in the GUI:
  - **Rename File Name Template** text box (below the Open Report /
    Open Log row) accepts a template string using `%Variable%` tokens.
    Valid tokens: `%File_Name%`, `%File_Extension%`, `%Date_YY%`,
    `%Date_YYYY%`, `%Date_MM%`, `%Date_DD%`, `%Camera_Make%`.
  - **Test Rename String** button validates the template and previews
    the first 10 rendered filenames from the current catalog workbook
    in the Process Log panel. Rows that can't render (e.g. missing
    `DateTimeOriginal`) are shown with a reason so the user can adjust
    the template before the full build.
  - **Build Renames for all Photos** button runs the template across
    every row in the workbook on a background thread, writes the
    rendered string into the `RenameFileName` cell, and saves the
    workbook in place. Rows with missing required data are left blank
    with a warning summarized in the log by reason.
  - Both rename buttons only activate once a catalog workbook exists
    on disk and a non-empty template is in the text box. They stay
    disabled during any running catalog / pre-scan / rename job.
  - Substituted values are stripped of path separators and Windows-
    illegal filename characters so the rendered string is always a
    valid filename.
  - The on-disk photo files are **not** moved or renamed by this
    feature — only the `RenameFileName` column in the workbook is
    populated. Actual file renames / moves are a planned follow-up.
  - New module: `scripts/rename_engine.py`
    (`validate_template`, `render_row`, `test_template`, `build_renames`).

### Added — Pre-Scan Folder

- **New "Pre-Scan Folder" button** to the left of "Start Cataloging
  Process." Pre-scan is a fast filesystem-metadata-only pass that
  reports, before any image is opened:
  - total folders scanned and total files encountered
  - supported image count broken down by extension
  - non-image files broken down by extension (so videos, PDFs, Word
    docs, etc. that shouldn't be in the photo folder can be surfaced
    and moved out before the real catalog runs)
- Pre-scan results stream live into the Process Log panel and are also
  written to the timestamped log file in the configured
  `log_file_folder`.
- **Two-stage button gating:** Pre-Scan Folder activates once both
  folder inputs are populated; Start Cataloging Process activates only
  after a successful pre-scan of the currently-selected photo folder.
  Editing the photo folder afterward invalidates the pre-scan so the
  user re-scans before cataloging.
- **Indeterminate progress bar** (marquee) during pre-scan with a
  running counter formatted as `Scanning… 8,231 files in 127 folders`,
  since the total isn't known until the walk finishes.
- Pre-scan runs on its own `QThread` and can be interrupted cleanly if
  the user closes the window mid-walk.
- **`photo_catalog.prescan_folder()`** and
  **`catalog_pipeline.run_prescan()`** added so CLI/GUI share the same
  pre-scan implementation with progress/log/cancel callbacks.

### Changed — Simpler EXIF output

- Removed seven low-signal EXIF fields from the Catalog sheet to shrink
  the workbook and make the remaining columns easier to sort/filter:
  `DateTimeDigitized`, `DateTimeModified`, `SubSecTimeOriginal`,
  `SubSecTimeDigitized`, `ExposureProgram`, `ExposureMode`,
  `MeteringMode`. Deleted the now-unused `EXIF_EXPOSURE_PROGRAMS`,
  `EXIF_METERING_MODES`, and `EXIF_EXPOSURE_MODE` lookup tables.
  `DateTimeOriginal` remains and is still formatted as an Excel date.

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
