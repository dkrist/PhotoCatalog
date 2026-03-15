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
- **Excel date formatting** — DateTimeOriginal, DateTimeDigitized, and DateTimeModified stored as proper Excel dates (sortable/filterable)

---

## Planned

### Phase 3 — Photo Organization
- **Date-based folder organization** — Rename and move photos into a YYYY-MM folder structure based on the date the picture was taken (DateTimeOriginal). Should handle missing dates gracefully and provide a summary of what was moved.

---

## Ideas / Future Phases
_Add ideas here as they come up. When an idea is ready to be worked on, move it into a Phase above and create a GitHub Issue for it._

- _(example) Duplicate photo detection_
- _(example) Export to CSV or HTML_
- _(example) GPS/location data extraction_