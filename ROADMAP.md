# PhotoCatalog Roadmap

This document tracks planned enhancements and completed milestones for the PhotoCatalog project.

Use [GitHub Issues](https://github.com/dkrist/PhotoCatalog/issues) for detailed discussion on individual features.

---

## Completed

### Phase 1 — Core Functionality
- Scan a photo folder and extract EXIF/XMP metadata
- Produce a formatted Excel spreadsheet with photo details
- Support for common image formats (JPG, PNG, TIFF, HEIC, etc.)
- Column ordering and human-readable value lookups via config.py

### Phase 2 — Usability Improvements
- **GUI folder picker** — tkinter dialog when no folder argument is passed
- **Excel date formatting** — DateTimeOriginal stored as proper Excel dates (sortable/filterable). _Note: redundant DateTimeDigitized / DateTimeModified columns were retired in v2.1.0 to slim the workbook._
- **Application settings (`settings.py`)** — JSON-based user config at `%APPDATA%\PhotoCatalog\config.json` with `save_report_to`, `log_file_folder`, `default_scan_folder`, `enable_face_recognition`, `log_level`, and recent folders
- **File logging** — timestamped log files written to the configured `log_file_folder`
- **Desktop UI (PyQt6)** — `gui_main.py` with folder pickers, progress bar, live log tail, and Open Report / Open Log buttons. Pipeline logic lives in `catalog_pipeline.py` and is shared with the CLI.
- **Windows installer / distribution** — PyInstaller `--onedir` build wrapped in an Inno Setup installer, orchestrated by `packaging\build.ps1`. Produces `release\PhotoCatalog-Setup-<version>.exe` ready for GitHub Releases. See `documentation/RELEASING.md` for the full workflow.

### Phase 2.1 — Whole-Drive Scanning & Pre-Scan (v2.1.0)
- **Recursive scanning fix** — whole drives and folders-of-folders now catalog correctly (`os.walk` with system/hidden-folder pruning) instead of returning "no images found."
- **Pre-Scan Folder** — a fast filesystem-only pass that reports folder count, total files, supported images by extension, and non-image files by extension before any catalog run, so stray videos/docs can be triaged out of the photo folder first. Results stream to the log panel and the rotating log file; an indeterminate progress bar with a `files/folders` counter shows liveness.
- **Two-stage UI gating** — Pre-Scan activates once the Save-Report folder is chosen; Start Cataloging activates only after a successful pre-scan of the currently-selected photo folder.
- **Slimmed EXIF output** — removed seven low-signal fields (`DateTimeDigitized`, `DateTimeModified`, `SubSecTimeOriginal`, `SubSecTimeDigitized`, `ExposureProgram`, `ExposureMode`, `MeteringMode`) from the Catalog sheet.
- **FileExtension column** — normalized lowercase-with-dot extension (`.jpg`, `.heic`, …) immediately right of `FileName`.
- **Rename template engine** — new `RenameFileName` column plus Rename File Name Template UI with `%File_Name%`, `%File_Extension%`, `%Date_YY%`, `%Date_YYYY%`, `%Date_MM%`, `%Date_DD%`, `%Camera_Make%` variables, a Test Rename String preview button, and a Build Renames for all Photos button that populates the column for every row in the workbook. Generates the strings only — no files are moved yet.

---

## Planned

### Phase 3 — Photo Organization
- **On-disk renames and moves** — apply the `RenameFileName` values generated in Phase 2.1 to the actual files, moving them into a YYYY-MM folder structure based on `DateTimeOriginal`. Needs collision handling, a dry-run preview, a manifest/undo log, and a summary of what was moved. Rows with blank `RenameFileName` will be reported rather than touched.

---

## Ideas / Future Phases
_Add ideas here as they come up. When an idea is ready to be worked on, move it into a Phase above and create a GitHub Issue for it._

- _(example) Duplicate photo detection_
- _(example) Export to CSV or HTML_
- _(example) GPS/location data extraction_