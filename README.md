# PhotoCatalog

A Windows desktop app that walks a folder (or a whole drive) of photos, reads EXIF / XMP metadata from each image, detects byte-identical duplicates, and either writes a single formatted Excel workbook for review or copies the entire library into a clean date-organized destination folder.

Built to make large family photo archives **browsable, sortable, and searchable in Excel** — and, as of v3, to **reorganize messy multi-decade photo drives** into a layout you actually want to live with — without any proprietary photo-management software.

![Photo Catalog UI](Images/Screenshot%202026-04-14%20192422.png)

---

## What's New in v3.0.0

v3 expands PhotoCatalog from "scan + rename in place" to a complete **scan → detect duplicates → reorganize** workflow:

- **Destination Folder + Folder Layout picker.** Choose a destination root, pick checkbox-driven year/month/day nesting and per-level format (`YYYY`, `MM - MonthName`, `YYYY-MM-DD`, etc.), and the app composes a clean target path for every photo with a live preview. New `File_DestFolder` and `File_DestPath` columns store the rendered targets.
- **Duplicate detection** with two modes: *Filename + Size* (fast pre-screen) and *MD5 Hash* (byte-identical, slower). Grouped duplicates are flagged in three new columns (`File_Hash`, `File_DupeGroup`, `File_DupeKeep`) and the `File_Name` cell of every grouped row is highlighted pale orange so duplicates jump off the page without sorting.
- **Detect Duplicates on Existing Workbook** button — re-runs detection against an already-saved workbook so you don't have to re-scan a multi-hour drive just because the dupe-mode combo was on *None* the first time.
- **Copy to Destination** button copies every catalog row to its `File_DestPath`, with same-stem **sidecar files** (RAW+JPG pairs, `.xmp`, `.aae`, `.thm`, `.dop`) following the primary, and automatic `_2`, `_3` suffixing if the target name already exists.
- **Move non-keepers** and **Delete non-keepers from source** buttons act on rows where `File_DupeKeep = FALSE`. Move relocates them to a holding folder for later review; Delete removes them from the source drive after a strong two-step confirmation.
- **Rollback journal + Undo Last Operation** button. Every Copy / Move / Delete pass writes a `_rollback_<timestamp>.jsonl` file in the destination; Undo replays the most recent journal in reverse.
- **`File_Status`** column tracks per-row state across the pipeline (`Pending`, `Copied`, `DupeMoved`, `DupeDeleted`, etc.).
- **Full UI-state persistence** — destination folder, layout choices, dupe mode, rename template, and operation defaults all round-trip through an app restart via `%APPDATA%\PhotoCatalog\settings.json`.

See the [v3.0.0 entry in the CHANGELOG](documentation/CHANGELOG.md) for the full breakdown.

---

## Features

### Scanning and metadata extraction (since v1)

- **Recursive whole-drive scanning** with automatic skipping of Windows system folders (`$RECYCLE.BIN`, `System Volume Information`), hidden folders, and common dev clutter (`.git`, `__pycache__`, `node_modules`, etc.).
- **Pre-Scan Folder** — a fast filesystem-only pass that reports folder count, total files, supported-image counts by extension, and non-image file types so stray videos, PDFs, or documents can be triaged out before the real catalog runs.
- **Broad format support**: JPG, JPEG, PNG, TIFF, HEIC, HEIF, WEBP, plus RAW formats CR2, CR3, NEF, ARW, DNG, ORF, RW2.
- **Resilient to malformed EXIF** — scanner-produced JPEGs, older cameras with NUL-padded Model tags, and other EXIF quirks no longer abort a long run; affected fields are left blank for the row and a `[WARN]` is added to `File_Concern`.
- **Optional face detection / recognition** (via the `face_recognition` library) writes face region counts and person names into the workbook.

### Excel output

- **Formatted Catalog and Summary sheets** with column ordering, alternating row fill, header styling, and `DateTimeOriginal` written as a real Excel datetime (sortable / filterable).
- **`File_` column block on the left** holds every app-generated and filesystem-sourced field (name, size, dates, hash, dupe group, destination path, status, concerns, source path) so EXIF/XMP camera fields don't crowd the most-used columns.
- **Color-coded concern flags** — pale yellow for `[INFO]`/`[WARN]`, red for `[ERROR]` — and pale orange highlight on `File_Name` for any row that's part of a duplicate group.

### Rename engine

- **Rename template engine** — construct new filenames from EXIF fields using `%Variable%` tokens (e.g. `%Date_YYYY%-%Date_MM%-%Date_DD%_%Camera_Make%_%File_Name%%File_Extension%`), preview the first 10 rows, then write rendered names into the `File_RenameName` column for every photo.
- **Pre-flight template validation** blocks empty templates, missing extensions, and unknown tokens before any rendering happens, and warns about templates likely to produce mass collisions.

### v3 reorganization workflow

- **Destination Folder picker** + **Folder Layout** checkboxes (Year / Month / Day) with per-level format radios (`YYYY`, `'YY`, `YYYY-MM`, `MM`, `MM - MonthName`, `MMM`, `MonthName`, `YYYY-MM-DD`, `MM-DD`, `DD`).
- **Duplicate detection** — *None*, *Filename + Size*, or *MD5 Hash*.
- **Copy to Destination** — bulk file copy with sidecar handling and automatic collision suffixing.
- **Move non-keepers...** and **Delete non-keepers from source** — disposal options for `File_DupeKeep = FALSE` rows.
- **Undo Last Operation** — reverse the most recent Copy/Move/Delete pass via the rollback journal.
- **Detect Duplicates on Existing Workbook** — add dupe columns to a workbook produced with detection off, no re-scan required.

### Operations

- **Responsive UI** — every long operation runs on a background thread with a live progress bar, streaming log panel, and a rotating timestamped log file saved to a configurable folder.
- **Cancellable workers** — a Cancel button stops scanning, hashing, copying, and undo passes between files without corrupting in-flight rows.
- **One-click Windows installer** built with PyInstaller + Inno Setup.

---

## Download and Install

The easiest way to get PhotoCatalog is to grab the prebuilt Windows installer:

1. Go to [Releases](https://github.com/dkrist/PhotoCatalog/releases) and download the latest `PhotoCatalog-Setup-<version>.exe`.
2. Double-click to install. The installer places a shortcut on your Start menu and Desktop.
3. Launch PhotoCatalog from the Start menu.

No Python or other dependencies are required on end-user machines — everything is bundled.

---

## Quick Start (v3 workflow)

The top-down order of the main window mirrors the workflow:

1. **Select Photo Folder** — the source drive or folder to catalog.
2. **Save Report to Folder** — where the Excel workbook (and rollback journals, if you copy/move/delete later) will be written.
3. **Duplicate Detection** combo — pick *None*, *Filename + Size (fast)*, or *MD5 Hash (thorough, slower)*. Hash mode reads every file, so save it for runs where byte-identical certainty matters.
4. **Pre-Scan Folder** — sanity-check what's in the folder before committing. The log panel reports totals, image counts by extension, and any other file types present.
5. **Start Cataloging Process** — the main run. Streams progress to the bar and log panel, and writes the workbook when done.
6. **Open Catalog Report** — opens the workbook in Excel for review.

For the optional rename step, fill in the **Rename File Name Template** (e.g. `%Date_YYYY%-%Date_MM%-%Date_DD%_%Camera_Make%_%File_Name%%File_Extension%`), click **Test Rename String** to preview the first 10 rows, then **Build Renames for all Photos** to fill the `File_RenameName` column for every row.

For the v3 reorganize-into-destination workflow:

7. **Destination Folder (for Copy pass)** — pick the clean target root.
8. **Destination Folder Layout** — check Year, Month, and/or Day, and pick a format for each. The preview label shows exactly what one example folder will look like.
9. **Detect Duplicates** *(optional)* — re-run detection against the existing workbook if you forgot to set the dupe-mode combo before cataloging, or want to switch from filename+size to hash.
10. **Copy to Destination** — copies every row to its `File_DestPath`, follows sidecars, suffixes collisions, and writes a rollback journal.
11. **Move non-keepers** *(optional)* — relocate `File_DupeKeep = FALSE` rows from the source drive to a holding folder for later review.
12. **Delete non-keepers from source** *(optional, two-step confirm)* — remove `File_DupeKeep = FALSE` rows from the source drive entirely.
13. **Undo Last Operation** — replays the newest rollback journal in reverse if you change your mind.

For the full workflow with screenshots and examples, see [documentation/USAGE.md](documentation/USAGE.md).

---

## Documentation

- **[USAGE.md](documentation/USAGE.md)** — end-user workflow and examples
- **[CHANGELOG.md](documentation/CHANGELOG.md)** — version history and release notes
- **[ROADMAP.md](ROADMAP.md)** — completed milestones and planned work
- **[v3_design_notes.md](documentation/v3_design_notes.md)** — design rationale and decision log for the v3 reorganization features
- **[RELEASING.md](documentation/RELEASING.md)** — how releases get built, tagged, and published
- **[Development_Environment_Guide.md](documentation/Development_Environment_Guide.md)** — setting up a local dev environment

---

## Building from Source

PhotoCatalog is written in Python 3.14 on top of PyQt6. Dependencies are listed in [`requirements.txt`](requirements.txt).

```bash
pip install -r requirements.txt
python scripts/gui_main.py
```

To produce a Windows installer yourself, see [`packaging/build.ps1`](packaging/build.ps1) and [RELEASING.md](documentation/RELEASING.md). The build pipeline is PyInstaller (`--onedir`) wrapped in Inno Setup, producing `release/PhotoCatalog-Setup-<version>.exe`.

### v3 module map

The v3 reorganization features are split across four new modules so they can be tested and evolved independently of the core scanner:

- **`scripts/duplicate_detector.py`** — MD5 hashing, group identification, keeper selection, and `detect_duplicates_on_workbook()` for after-the-fact detection on an existing workbook.
- **`scripts/folder_composer.py`** — `FolderConfig` dataclass and the path-building logic that turns a date + layout config into a destination folder string.
- **`scripts/copy_engine.py`** — `copy_to_destination()`, `move_non_keepers()`, `delete_non_keepers()`, with sidecar handling and per-row `File_Status` updates.
- **`scripts/rollback.py`** — JSONL journal writer and `undo_journal()` dispatch table.

The catalog pipeline (`scripts/catalog_pipeline.py`) orchestrates all of these as optional phases — callers that don't pass `dupe_mode`, `folder_config`, or `destination_folder` get v2.1.x behavior unchanged.

---

## Smart Hash Strategy

MD5 hashing is by far the slowest phase in the pipeline — every file has to be read off the source drive end-to-end — so on a 50,000-photo library the naive "hash everything" approach can run for many minutes before duplicate detection has anything to compare. v3 ships with an **opt-out optimization** that typically eliminates 80–95% of that I/O without changing the result.

### The insight

Two files cannot be byte-identical unless they have the **same size in bytes**. The filesystem already knows the size of every file (it's free metadata, no disk read required), and the catalog's Phase 1 metadata pass has already populated `File_SizeBytes` on every row before hashing starts. So before we hash anything, we can bucket every row by `File_SizeBytes` and observe that any size-bucket containing only one row cannot possibly produce a duplicate group — that file is mathematically guaranteed to have no byte-identical twin in the library.

In a typical real-world photo archive the vast majority of files have a unique size (thanks to camera sensor noise, EXIF embedded thumbnails, and slight differences in JPEG compression even for visually identical scenes), so the set of rows that actually need to be hashed shrinks dramatically.

### How it works in v3

When `dupe_mode = "hash"` (either via the catalog run or via the standalone *Detect Duplicates on Existing Workbook* button), the pipeline:

1. Collects all `File_SizeBytes` values into size-buckets in memory.
2. Builds the **candidate set** — every path whose size collides with at least one other row.
3. Logs the savings up front, e.g. `Smart-hash optimization: hashing 3,142 of 50,000 files (46,858 unique-size rows skipped, 93.7% I/O saved).`
4. Hashes only the candidate paths, with the progress bar tracking against the candidate count rather than the total row count so the percentage and ETA stay meaningful.
5. Runs the existing keeper-selection / group-numbering logic against the (now correctly populated) `File_Hash` column. Rows skipped by the optimization keep an empty `File_Hash` cell, which is correct because they cannot be in any duplicate group.

The user can opt out via the new **Hash all files** checkbox next to the Duplicate Detection combo. When ticked, the candidate filter is bypassed and every file is hashed — useful when the user wants `File_Hash` populated for every row regardless of duplicate detection (for example, to use the workbook as input to an external integrity-checking workflow). The setting is persisted across launches via `%APPDATA%\PhotoCatalog\settings.json`.

### Correctness guarantee

The optimization is **provably lossless** for duplicate detection: skipping a row whose size is unique cannot cause a missed duplicate group, because the necessary precondition for membership in a group (matching `File_SizeBytes` on at least one other row) was never satisfied. The only observable difference between optimized and unoptimized runs is the `File_Hash` cell on size-unique rows, which the optimized path leaves blank and the unoptimized path fills in with an MD5 that nothing else in the workbook will ever match against.

### Credit

The size-bucket pre-screening approach, the opt-out checkbox UX, the progress-against-candidate-count behavior, and this README writeup were all designed by [Claude](https://www.anthropic.com/claude) in collaboration with the author. The implementation lives in `duplicate_detector.size_collision_candidates()` and the surrounding `populate_hashes()` filter, and is wired through `catalog_pipeline.run_catalog()` and the `DetectDupesWorker` GUI handler.

---

## Compatibility

- **Operating system:** Windows 10 / 11 (the bundled installer is Windows-only; the Python source runs on macOS and Linux for development purposes).
- **Workbook format:** v2.1.x workbooks open in v3 unchanged. v3 columns (`File_Hash`, `File_DupeGroup`, `File_DupeKeep`, `File_DestFolder`, `File_DestPath`, `File_Status`) are appended on load if they're missing, so a v2.1 catalog can be promoted into the v3 workflow without re-scanning.
- **Settings file:** `%APPDATA%\PhotoCatalog\settings.json` is shared across versions — unknown future keys survive a save-load round-trip, and the v3 keys default to safe values when read by older builds.

---

## Built with Claude

PhotoCatalog was designed and implemented in close collaboration with [Claude](https://www.anthropic.com/claude), Anthropic's AI assistant — used throughout for architecture discussions, code generation, debugging, documentation, and release engineering. The "Built with Claude" mark and Claude wordmark in the application header reflect that partnership.

Change requests were written in a structured PM-style format, discussed with Claude for clarifying questions and trade-offs, and then implemented and tested collaboratively. The [CHANGELOG](documentation/CHANGELOG.md) captures the evolution of the app through that process.

<sub>Claude, Anthropic, and the Claude wordmark are trademarks of Anthropic. This project is an independent effort that uses Claude as a development tool.</sub>

---

## Author

**David Krist** — [github.com/dkrist](https://github.com/dkrist)

---

## License

A license for this project has not been selected yet. Until one is added, all rights are reserved by the author. If you would like to use, fork, or redistribute the code, please open an issue to discuss.
