# Photo Catalog App — Project Documentation

## Overview

A desktop utility that scans a user-selected folder of photos, reads all available metadata (EXIF, IPTC, and XMP) from each image file, and exports a single Excel spreadsheet with one row per photo and columns for every metadata field found.

The goal is to give photographers and photo archivists a fast, no-nonsense way to inventory a photo library with full technical and descriptive metadata — no database setup, no cloud service, just folder in → spreadsheet out.

---

## Target Users

- Photographers who want to audit or inventory a shoot
- Archivists cataloging image collections
- Anyone who needs a structured spreadsheet of photo metadata for sorting, filtering, or analysis

---

## Core Workflow

```
1. User launches the app
2. User selects a folder (via file picker dialog)
3. App scans the folder for supported image files
4. For each image, app extracts all available metadata
5. App writes an Excel (.xlsx) file with one row per photo
6. User opens the spreadsheet to browse, filter, and sort
```

---

## Supported File Types

| Format | Extensions | Notes |
|--------|-----------|-------|
| JPEG | `.jpg`, `.jpeg` | Most common; full EXIF/XMP/IPTC support |
| TIFF | `.tif`, `.tiff` | Full metadata support |
| PNG | `.png` | Limited EXIF; may contain XMP |
| HEIF/HEIC | `.heif`, `.heic` | Apple's default format since iPhone 11 |
| WebP | `.webp` | Growing adoption; limited metadata |
| RAW formats | `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2` | Camera-specific RAW files; rich metadata |

Videos (`.mp4`, `.mov`) are skipped by default but could be supported in a future version.

---

## Metadata Fields to Extract

The app should extract every available field across three metadata standards. Below is the full target field list, organized by category.

### EXIF (Camera & Technical Data)

| Column Name | EXIF Tag | Example Value |
|------------|----------|---------------|
| `FileName` | (derived) | `IMG_0465.jpg` |
| `FilePath` | (derived) | `/Users/david/Photos/IMG_0465.jpg` |
| `FileSize` | (derived) | `3.2 MB` |
| `ImageWidth` | ExifImageWidth | `5712` |
| `ImageHeight` | ExifImageHeight | `4284` |
| `CameraMake` | Make | `Apple` |
| `CameraModel` | Model | `iPhone 16 Pro Max` |
| `LensMake` | LensMake | `Apple` |
| `LensModel` | LensModel | `iPhone 16 Pro Max back triple camera 6.765mm f/1.78` |
| `LensSpec` | LensSpecification | `2.22-15.66mm f/1.78-2.8` |
| `Software` | Software | `26.0.1` |
| `DateTimeOriginal` | DateTimeOriginal | `2025:11:23 09:26:37` |
| `DateTimeDigitized` | DateTimeDigitized | `2025:11:23 09:26:37` |
| `DateTimeModified` | DateTime | `2025:11:23 09:26:37` |
| `OffsetTime` | OffsetTime | `-08:00` |
| `SubSecTimeOriginal` | SubsecTimeOriginal | `688` |
| `ExposureTime` | ExposureTime | `1/4975` |
| `FNumber` | FNumber | `1.78` |
| `ISO` | ISOSpeedRatings | `80` |
| `ShutterSpeed` | ShutterSpeedValue | `12.28` |
| `Aperture` | ApertureValue | `1.66` |
| `Brightness` | BrightnessValue | `9.89` |
| `ExposureBias` | ExposureBiasValue | `0.0` |
| `ExposureProgram` | ExposureProgram | `Normal program` |
| `ExposureMode` | ExposureMode | `Auto` |
| `MeteringMode` | MeteringMode | `Pattern` |
| `Flash` | Flash | `No flash, compulsory` |
| `FocalLength` | FocalLength | `6.77 mm` |
| `FocalLengthIn35mm` | FocalLengthIn35mmFilm | `24 mm` |
| `WhiteBalance` | WhiteBalance | `Auto` |
| `SceneCaptureType` | SceneCaptureType | `Standard` |
| `SensingMethod` | SensingMethod | `One-chip color area` |
| `ColorSpace` | ColorSpace | `Uncalibrated` |
| `CompositeImage` | CompositeImage | `2` |
| `Orientation` | Orientation | `Horizontal` |
| `XResolution` | XResolution | `72` |
| `YResolution` | YResolution | `72` |

### GPS Data

| Column Name | EXIF Tag | Example Value |
|------------|----------|---------------|
| `GPSLatitude` | GPSLatitude | `37.7749` |
| `GPSLongitude` | GPSLongitude | `-122.4194` |
| `GPSAltitude` | GPSAltitude | `52.3 m` |
| `GPSSpeed` | GPSSpeed | `0.0` |
| `GPSImgDirection` | GPSImgDirection | `245.67` |
| `GPSDateStamp` | GPSDateStamp | `2025:11:23` |

### IPTC (Descriptive & Rights)

| Column Name | IPTC Field | Example Value |
|------------|-----------|---------------|
| `Title` | Object Name | `Sunset at Baker Beach` |
| `Description` | Caption/Abstract | `Golden hour photo overlooking...` |
| `Keywords` | Keywords | `sunset, beach, golden gate` |
| `Creator` | By-line | `David Krist` |
| `CreatorJobTitle` | By-line Title | `Photographer` |
| `CopyrightNotice` | Copyright Notice | `© 2025 David Krist` |
| `CreditLine` | Credit | `David Krist Photography` |
| `Source` | Source | `Original` |
| `Headline` | Headline | `Baker Beach Sunset` |
| `Instructions` | Special Instructions | `Not for commercial use` |
| `City` | City | `San Francisco` |
| `State` | Province/State | `California` |
| `Country` | Country | `United States` |
| `CountryCode` | Country Code | `US` |
| `Sublocation` | Sub-location | `Baker Beach` |
| `DateCreated` | Date Created | `2025-11-23` |
| `IntellectualGenre` | Intellectual Genre | `Landscape` |
| `IPTCScene` | Scene | `011100` |
| `IPTCSubjectCode` | Subject Code | `060000` |

### XMP (Extended & Editing Metadata)

| Column Name | XMP Namespace | Example Value |
|------------|--------------|---------------|
| `XMP_CreatorTool` | xmp:CreatorTool | `26.0.1` |
| `XMP_CreateDate` | xmp:CreateDate | `2025-11-23T09:26:37` |
| `XMP_ModifyDate` | xmp:ModifyDate | `2025-11-23T09:26:37` |
| `XMP_Rating` | xmp:Rating | `4` |
| `XMP_Label` | xmp:Label | `Blue` |
| `PS_DateCreated` | photoshop:DateCreated | `2025-11-23T09:26:37` |
| `DC_Title` | dc:title | `My Photo Title` |
| `DC_Description` | dc:description | `Description text` |
| `DC_Creator` | dc:creator | `David Krist` |
| `DC_Subject` | dc:subject | `sunset, beach` |
| `DC_Rights` | dc:rights | `© 2025 David Krist` |
| `LR_HierarchicalSubject` | lr:hierarchicalSubject | `Places\|California\|SF` |
| `FaceRegions` | mwg-rs:Regions | `4 faces detected` |
| `FaceRegionCount` | (derived) | `4` |

### Dynamic Column Handling

Since XMP is extensible, the app should also capture any non-standard XMP namespaces found and add them as additional columns dynamically. This ensures nothing is lost even for files with unusual or proprietary metadata (e.g., Apple's `apple-fi:` face info, Adobe Lightroom develop settings, etc.).

---

## Excel Output Specification

### File Naming
```
PhotoCatalog_[FolderName]_[YYYY-MM-DD].xlsx
```
Example: `PhotoCatalog_Claude Photos_2026-03-03.xlsx`

### Sheet Structure

**Sheet 1: "Catalog"** — Main data (one row per photo, all metadata columns)

**Sheet 2: "Summary"** — Aggregate stats:
- Total photo count
- Date range (earliest → latest photo)
- Camera models used (with counts)
- Lens models used (with counts)
- ISO range (min / max / average)
- GPS coverage (how many photos have coordinates)
- Top 10 keywords (if IPTC keywords exist)

### Formatting
- Header row: bold, frozen, with auto-filter enabled
- Date columns: formatted as dates (not raw strings)
- GPS columns: formatted as decimal degrees (6 decimal places)
- Column widths: auto-fit to content
- Conditional formatting: highlight rows missing GPS data (optional)

---

## Current Status

**Phase 1 MVP is complete.** The app successfully scans a folder, extracts metadata from all supported image types, and produces a fully formatted Excel spreadsheet. It was built and tested against a real library of 542 iPhone photos on 2026-03-03.

### What's Working

- Folder scanning with file-type filtering (12 image formats supported)
- EXIF extraction via Pillow (camera, lens, exposure, GPS, timestamps — 30+ fields)
- XMP extraction via raw byte parsing + xml.etree (face regions, creator tool, dates)
- Dynamic column discovery (57 columns found in test run)
- Human-readable value mapping (exposure programs, metering modes, flash modes, etc.)
- GPS coordinate conversion (DMS → decimal degrees)
- Excel output with two sheets (Catalog + Summary)
- Formatted headers (frozen, auto-filtered, styled)
- Alternating row colors for readability
- Summary sheet with camera stats, exposure ranges, GPS coverage, face detection counts
- Console progress reporting for large folders

### What's Not Yet Built

- GUI folder picker (currently CLI-only)
- IPTC field extraction (fields are defined but iPhone photos don't populate them)
- Recursive subfolder scanning
- Error logging for corrupt/unreadable files
- Standalone packaging (PyInstaller)

---

## Technical Architecture

### Current Tech Stack (v0.1)

| Component | Technology | Status |
|-----------|-----------|--------|
| Language | Python 3.10+ | Implemented |
| EXIF extraction | `Pillow` (PIL) | Implemented |
| XMP extraction | `xml.etree.ElementTree` (raw byte parsing) | Implemented |
| Excel output | `openpyxl` | Implemented |
| Configuration | `config.py` (constants + mappings) | Implemented |
| CLI runner | `run_catalog.py` (inbox → output wrapper) | Implemented |
| Folder picker GUI | `tkinter` | Planned |
| ExifTool integration | `PyExifTool` | Planned (optional upgrade) |
| Packaging | `PyInstaller` or `cx_Freeze` | Planned |

### Why Pure Python First?

The initial build uses Pillow + raw XMP parsing instead of ExifTool. This keeps the dependency footprint minimal (just `pip install`) with no system-level installs required. ExifTool can be added later as an optional upgrade for deeper metadata coverage (MakerNote, sidecar files, video metadata).

### Application Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  CLI / inbox │────▶│  Scan for    │────▶│  Extract     │────▶│  Write      │
│  folder arg  │     │  image files │     │  EXIF + XMP  │     │  Excel file │
│              │     │  (os.listdir)│     │  (Pillow +   │     │  (openpyxl) │
│              │     │              │     │   xml.etree) │     │             │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
                                               │
                                               ▼
                                         ┌──────────────┐
                                         │  Normalize   │
                                         │  field names │
                                         │  & values    │
                                         └──────────────┘
```

### Key Design Decisions

1. **Pure Python extraction** — Uses Pillow for EXIF and raw byte scanning + xml.etree for XMP. No system dependencies required. ExifTool can be added later as an optional upgrade path.

2. **Dynamic columns** — Don't hardcode the column list. Read the union of all fields found across all photos, then use that as the column set. This ensures no metadata is silently dropped. (57 columns discovered in first real test.)

3. **Normalized column names** — Map EXIF tag IDs to clean, readable column headers (like `FocalLength_mm`, `GPSAltitude_m`). Maintain lookup dictionaries for coded values (exposure programs, flash modes, etc.) and pass through unknown fields as-is.

4. **Progress feedback** — Console output every 50 files so the user knows it's working on large folders.

5. **Inbox/output workflow** — The `run_catalog.py` wrapper defaults to scanning the `inbox/` folder and writing results to `output/`, keeping the project folder clean.

---

## Project Structure

```
PhotoCatalog/
├── inbox/                   # Drop photos here to catalog them
├── scripts/
│   ├── photo_catalog.py     # Core logic — scanning, extraction, Excel writing
│   ├── run_catalog.py       # Quick-run wrapper (inbox → output)
│   └── config.py            # Supported extensions, field mappings, constants
├── documentation/
│   ├── Photo_Catalog_App_Project.md   # This file — full project spec
│   ├── USAGE.md                       # User-facing usage guide
│   └── CHANGELOG.md                   # Version history
├── output/                  # Generated spreadsheets land here
├── tests/                   # Unit tests (future)
└── requirements.txt         # Python dependencies
```

---

## Dependencies

### Required (current)
```
openpyxl>=3.1.0       # Excel file generation with formatting
Pillow>=10.0.0        # EXIF metadata extraction from images
```

No system-level dependencies required for the current pure-Python implementation.

### Optional (future upgrade)
```
PyExifTool>=0.5.6     # Deeper metadata via ExifTool (requires system install)
```

System dependency for ExifTool path: `brew install exiftool` (macOS), `apt install libimage-exiftool-perl` (Linux), or [exiftool.org](https://exiftool.org/) (Windows).

---

## Milestone Plan

### Phase 1 — Core MVP ✅ COMPLETE (2026-03-03)
- [x] Scan folder for supported image types (12 formats)
- [x] Extract EXIF metadata via Pillow (30+ fields with human-readable mappings)
- [x] Extract XMP metadata via raw byte parsing + xml.etree
- [x] Dynamic column discovery (union of all fields across all photos)
- [x] Normalize field names with mapping dictionaries
- [x] Write Excel file with Catalog sheet (one row per photo)
- [x] Auto-fit columns, bold headers, frozen row, auto-filter
- [x] GPS coordinate conversion (DMS → decimal degrees)
- [x] Summary sheet with aggregate stats
- [x] Console progress reporting
- [x] Project folder structure (inbox → scripts → output)
- [x] Quick-run wrapper script (run_catalog.py)
- [x] Config module with all constants and mappings
- [x] Usage guide documentation
- **Delivered:** Working CLI app, tested on 542 photos, producing 57-column spreadsheet

### Phase 2 — Polish & Robustness
- [x] GUI folder picker dialog (tkinter)
- [ ] Handle edge cases: corrupt files, missing metadata, permission errors
- [ ] Add error log sheet (skipped files with reasons)
- [ ] IPTC field extraction (for Lightroom/Bridge-processed photos)
- [x] Date columns as proper Excel date format (not strings)

### Phase 3 — Distribution
- [ ] Package as standalone executable (PyInstaller)
- [ ] macOS `.app` bundle and/or Windows `.exe`
- [ ] User README with screenshots
- [ ] Optional: drag-and-drop folder support

### Phase 4 — Future Ideas
- [ ] Recursive subfolder scanning (optional toggle)
- [ ] Thumbnail column in Excel (small embedded image per row)
- [ ] Video file support (`.mp4`, `.mov` metadata)
- [ ] CSV export option alongside Excel
- [ ] Duplicate detection (by hash or by matching metadata)
- [ ] Map view HTML export (photos plotted on a map by GPS)
- [ ] Lightroom/Capture One XMP sidecar file support

---

## Test Results (2026-03-03)

First full run against a real photo library:

| Metric | Value |
|--------|-------|
| Photos processed | 542 |
| Columns extracted | 57 |
| Cameras found | iPhone 16 Pro Max (458), iPhone 15 Pro Max (73) |
| Date span | Nov 22–27, 2025 (5 days) |
| ISO range | 20 – 2000 (avg 138) |
| Aperture range | f/1.78 – f/2.2 |
| Focal length range | 14mm – 99mm (35mm equiv) |
| GPS coverage | 32 of 542 photos (6%) |
| Lenses used | 6 distinct lens configurations |
| Face detection | Present in many photos (Apple mwg-rs:Regions) |

**EXIF fields extracted:** CameraMake, CameraModel, HostComputer, Software, LensMake, LensModel, LensSpec, DateTimeOriginal, DateTimeDigitized, DateTimeModified, OffsetTime (x3), SubSecTime (x2), ExposureTime, FNumber, ISO, ShutterSpeed, Aperture, Brightness, ExposureBias, ExposureProgram, ExposureMode, MeteringMode, Flash, FocalLength_mm, FocalLength35mm, WhiteBalance, SceneCaptureType, SensingMethod, ColorSpace, CompositeImage, Orientation, XResolution, YResolution, SubjectLocation, GPS (latitude, longitude, altitude, speed, direction, date)

**XMP fields extracted:** xmp:CreatorTool, xmp:CreateDate, xmp:ModifyDate, photoshop:DateCreated, exif:CompositeImage, mwg-rs:Regions (face detection with Apple Face ID references), FaceRegionCount, HasFaceRegions

IPTC fields are defined in the spec but were empty in this test library (typical for unprocessed iPhone photos — they get populated by editing software like Lightroom or Bridge).

---

## References

- [IPTC Photo Metadata Standard 2025.1](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata)
- [IPTC Photo Metadata User Guide](http://iptc.org/std/photometadata/documentation/userguide/)
- [ExifTool by Phil Harvey](https://exiftool.org/)
- [Mastering Photo Metadata — EXIFData.org](https://exifdata.org/blog/mastering-photo-metadata-a-guide-to-exif-iptc-and-xmp-data-standards)
- [Photo Metadata Field Guide — Photometadata.org](http://www.photometadata.org/META-Resources-Field-Guide-to-Metadata)
