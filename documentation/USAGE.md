# Photo Catalog — Usage Guide

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Drop photos into the inbox

Copy or move any photos you want to catalog into the `inbox/` folder.

### 3. Run the catalog

```bash
# Catalog photos in the inbox (default)
python scripts/run_catalog.py

# Catalog any folder you choose
python scripts/run_catalog.py /path/to/your/photos
```

### 4. Find your spreadsheet

The output Excel file will be saved to the `output/` folder, named:
```
PhotoCatalog_[FolderName]_[YYYY-MM-DD].xlsx
```

## Folder Structure

```
PhotoCatalog/
├── inbox/              ← Drop photos here to catalog them
├── scripts/            ← Python source code
│   ├── photo_catalog.py    Main extraction + Excel writing logic
│   ├── run_catalog.py      Quick-run wrapper (inbox → output)
│   └── config.py           Supported types, field mappings, constants
├── documentation/      ← Project docs
│   ├── Photo_Catalog_App_Project.md   Full project spec
│   └── USAGE.md                       This file
├── output/             ← Generated spreadsheets land here
├── tests/              ← Unit tests (future)
└── requirements.txt    ← Python dependencies
```

## Supported File Types

JPEG, TIFF, PNG, HEIF/HEIC, WebP, and RAW formats (CR2, CR3, NEF, ARW, DNG, ORF, RW2).

Videos (.mp4, .mov) are skipped for now.

## What Gets Extracted

The app pulls metadata from three standards:

- **EXIF** — camera, lens, exposure, ISO, focal length, GPS, timestamps
- **XMP** — creator tool, ratings, labels, face regions, Dublin Core fields
- **IPTC** — titles, keywords, copyright, location (if present in the file)

Any fields not in the predefined list are still captured as dynamic columns, so nothing gets lost.

## Output

The Excel file has two sheets:

- **Catalog** — One row per photo, all metadata as columns. Headers are frozen with auto-filter.
- **Summary** — Aggregate stats: photo count, date range, cameras used, ISO/aperture/focal length ranges, GPS coverage, face detection counts.
