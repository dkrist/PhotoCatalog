# Changelog

All notable changes to the Photo Catalog App project are documented in this file.

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
