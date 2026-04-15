# PhotoCatalog

A Windows desktop app that walks a folder (or a whole drive) of photos, reads EXIF / XMP metadata from each image, and writes a single formatted Excel workbook summarizing the library — one row per photo, columns for camera, lens, dates, exposure, GPS, face regions, and more.

Built to make large family photo archives **browsable, sortable, and searchable in Excel** without any proprietary photo-management software.

![Photo Catalog UI](Images/Screenshot%202026-04-14%20192422.png)

---

## Features

- **Recursive whole-drive scanning** with automatic skipping of Windows system folders (`$RECYCLE.BIN`, `System Volume Information`), hidden folders, and common dev clutter (`.git`, `__pycache__`, `node_modules`, etc.).
- **Pre-Scan Folder** — a fast filesystem-only pass that reports folder count, total files, supported-image counts by extension, and non-image file types (so stray videos, PDFs, or documents can be triaged out of the photo folder before the real catalog runs).
- **Formatted Excel output** with column ordering, alternating row fill, header styling, and `DateTimeOriginal` written as a real Excel date (sortable / filterable).
- **Broad format support**: JPG, JPEG, PNG, TIFF, HEIC, HEIF, WEBP, plus RAW formats CR2, CR3, NEF, ARW, DNG, ORF, RW2.
- **Optional face detection / recognition** (via the `face_recognition` library) writes face region counts and person names into the workbook.
- **Rename template engine** — construct new filenames from EXIF fields using `%Variable%` tokens (e.g. `%Date_YYYY%-%Date_MM%-%Date_DD%_%Camera_Make%_%File_Name%%File_Extension%`), preview the first 10 rows, then write rendered names into a dedicated `RenameFileName` column for every photo. On-disk file moves are a planned follow-up — this step gives you a review-and-revise column in the workbook first.
- **Resilient to malformed EXIF** — scanner-produced JPEGs, older cameras with NUL-padded Model tags, and other EXIF quirks no longer abort a long run; affected rows are left blank for those fields and logged.
- **Responsive UI** — every long operation runs on a background thread with a live progress bar, streaming log panel, and a rotating timestamped log file saved to a configurable folder.
- **One-click Windows installer** built with PyInstaller + Inno Setup.

---

## Download and Install

The easiest way to get PhotoCatalog is to grab the prebuilt Windows installer:

1. Go to [Releases](https://github.com/dkrist/PhotoCatalog/releases) and download the latest `PhotoCatalog-Setup-<version>.exe`.
2. Double-click to install. The installer places a shortcut on your Start menu and Desktop.
3. Launch PhotoCatalog from the Start menu.

No Python or other dependencies are required on end-user machines — everything is bundled.

---

## Quick Start

1. Click **Browse** next to *Select Photo Folder* and choose the folder (or drive root) you want to catalog.
2. Click **Browse** next to *Save Report to Folder* and choose where the Excel file should be written.
3. Click **Pre-Scan Folder** to see what's in the folder before committing — the Process Log panel will show totals, supported-image counts by extension, and any other file types present.
4. Click **Start Cataloging Process**. Progress streams to the progress bar and the log panel; you can open the timestamped log file any time.
5. When it finishes, click **Open Catalog Report** to open the Excel workbook.

For the optional filename-rename step, type a template (e.g. `%Date_YYYY%-%Date_MM%-%Date_DD%_%Camera_Make%_%File_Name%%File_Extension%`) into the *Rename File Name Template* box, click **Test Rename String** to preview the first 10 rows, then click **Build Renames for all Photos** to fill the `RenameFileName` column for every row in the workbook.

For the full workflow with screenshots and examples, see [documentation/USAGE.md](documentation/USAGE.md).

---

## Documentation

- **[USAGE.md](documentation/USAGE.md)** — end-user workflow and examples
- **[CHANGELOG.md](documentation/CHANGELOG.md)** — version history and release notes
- **[ROADMAP.md](ROADMAP.md)** — completed milestones and planned work
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
