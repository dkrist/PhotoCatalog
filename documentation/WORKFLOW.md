# PhotoCatalog — Process Workflow Guide

This document describes the step-by-step workflow of the PhotoCatalog application, including what each button does, what enables it, and the intended order of operations.

## Workflow Overview

PhotoCatalog processes photos in a pipeline. Each step builds on the output of the previous one. The buttons in the UI enable progressively as their prerequisites are met.

```
Select Folders
      |
      v
 Pre-Scan Folder ──> Start Cataloging Process
                            |
                            v
                   Open Catalog Report / Open Process Log
                            |
                     +------+------+
                     |             |
                     v             v
           Rename Templates   Detect Duplicates
                                   |
                     +-------------+-------------+
                     |             |             |
                     v             v             v
              Copy to        Move non-      Delete non-
              Destination    keepers         keepers
                     |             |             |
                     +-------------+-------------+
                                   |
                                   v
                          Undo Last Operation
```

## Step-by-Step Reference

### 1. Select Folders

Before any processing can begin, you need to configure two folder paths:

- **Select Photo Folder** — The source folder containing photos to catalog. Supports recursive scanning of subfolders.
- **Save Report to Folder** — Where the output Excel workbook will be saved.

**Enables:** Pre-Scan Folder button (once both folders are set).

### 2. Pre-Scan Folder

**Button:** Pre-Scan Folder
**Requires:** Both Photo Folder and Report Folder filled in with valid paths.

Performs a fast filesystem-only pass over the photo folder. Reports folder count, total files, supported images by extension, and non-image files. No EXIF extraction occurs — this is a quick sanity check so you can verify the folder contents before committing to a full catalog run.

Results stream to the log panel and the rotating log file. An indeterminate progress bar shows liveness during the scan.

**Enables:** Start Cataloging Process button (for the scanned folder).

### 3. Start Cataloging Process

**Button:** Start Cataloging Process
**Requires:** A successful pre-scan of the currently selected photo folder.

Runs the full cataloging pipeline: scans every supported image in the photo folder, extracts EXIF/XMP metadata, and writes a formatted Excel workbook to the report folder. The workbook contains one row per photo with columns for file info, camera data, exposure settings, GPS coordinates, face regions, and more.

If a Destination Folder and Folder Layout are configured, the workbook also includes `File_DestFolder` and `File_DestPath` columns pre-computed for the copy pass.

If Duplicate Detection is set to anything other than "None," duplicate detection runs as part of the catalog and populates `File_Hash`, `File_DupeGroup`, and `File_DupeKeep` columns.

**Produces:** An Excel workbook (`.xlsx`) in the report folder.
**Enables:** Open Catalog Report, Open Process Log, Detect Duplicates, and (if a Destination Folder is also set) Copy / Move / Delete / Undo buttons.

### 4. Open Catalog Report / Open Process Log

**Buttons:** Open Catalog Report, Open Process Log
**Requires:** A completed cataloging run (success, failure, or cancellation for the log).

- **Open Catalog Report** opens the generated Excel workbook in your default spreadsheet application.
- **Open Process Log** opens the timestamped log file for the current session in your default text editor. The log captures every step of the pipeline including warnings and errors — useful for troubleshooting.

### 5. Rename File Name Template (Optional)

**Buttons:** Test Rename String, Build Renames for all Photos
**Requires:** A workbook on disk AND a non-empty template string in the text box.

Lets you define a naming template using variables like `%Date_YYYY%`, `%Camera_Make%`, and `%File_Name%`. The template engine generates a `File_RenameName` value for every row in the workbook.

Available variables:

| Variable | Description | Example |
|---|---|---|
| `%File_Name%` | Original filename (no extension) | `IMG_1234` |
| `%Date_YY%` | 2-digit year from DateTimeOriginal | `26` |
| `%Date_YYYY%` | 4-digit year | `2026` |
| `%Date_MM%` | 2-digit month | `04` |
| `%Date_DD%` | 2-digit day | `09` |
| `%Camera_Make%` | Camera manufacturer | `Canon` |

- **Test Rename String** — Previews the template against the first photo in the workbook so you can verify the output format before applying to all rows.
- **Build Renames for all Photos** — Populates the `File_RenameName` column for every row. Generates strings only; no files are moved or renamed on disk.

### 6. Destination Folder and Folder Layout (Optional)

**Requires:** No prerequisites — configure any time before running Copy.

- **Destination Folder** — Where photos will be copied to during the Copy pass.
- **Destination Folder Layout** — Controls the subfolder structure at the destination. Check/uncheck Year, Month, and Day levels and pick a format for each from the dropdown:
  - **Year:** `YYYY` (2019) or `YY` (19)
  - **Month:** `MM` (06), `MM - MonthName` (06 - June), or `MonthName` (June)
  - **Day:** `DD` (15)

The **Example** preview at the bottom updates live as you change settings, showing what the folder path would look like for a sample date (June 15, 2019).

### 7. Duplicate Detection

**Combo:** Duplicate Detection (None / Filename + Size / MD5 Hash)
**Checkbox:** Hash all files

The duplicate detection mode can be set before cataloging (it runs as part of the pipeline) or applied afterward using the Detect Duplicates button.

- **None** — No duplicate detection.
- **Filename + Size (fast)** — Groups files that share the same name and byte size. Quick but may miss renamed duplicates.
- **MD5 Hash (thorough, slower)** — Computes file checksums for byte-exact matching. By default, files with a unique size are skipped (they cannot have a duplicate). Check "Hash all files" to force a full sweep.

**Button:** Detect Duplicates
**Requires:** A workbook on disk.

Runs duplicate detection against the existing workbook and populates `File_Hash`, `File_DupeGroup`, and `File_DupeKeep` columns. Useful when the original catalog was produced with detection set to "None."

### 8. Process Action Buttons

These five buttons operate on the workbook and the destination folder. They appear in the intended order of use.

#### Detect Duplicates

See Section 7 above.

#### Copy to Destination

**Requires:** A workbook on disk AND a Destination Folder.

Copies photos from the source folder to the destination, placing them into the subfolder structure defined by the Folder Layout settings. Updates the `File_Status` column in the workbook to track which files have been copied.

#### Move non-keepers

**Requires:** A workbook on disk AND a Destination Folder. At click time, also requires that duplicate detection has been run (so `File_DupeKeep` values exist).

Moves files marked as non-keepers (duplicates where `File_DupeKeep = FALSE`) to a `_non_keepers` subfolder in the destination. This separates duplicates from the main collection without deleting them.

#### Delete non-keepers

**Requires:** Same as Move non-keepers.

Permanently deletes files marked as non-keepers. Use with caution — this cannot be undone except via the Undo mechanism if a rollback journal exists.

#### Undo Last Operation

**Requires:** A workbook on disk AND a Destination Folder. At click time, requires a rollback journal to exist.

Reverses the most recent Copy, Move, or Delete operation using the rollback journal written during that operation. Only the last operation can be undone.

## Button Enable Summary

| Button | Enabled When |
|---|---|
| Pre-Scan Folder | Photo Folder + Report Folder set |
| Start Cataloging | Pre-scan completed for current folder |
| Open Catalog Report | Cataloging completed successfully |
| Open Process Log | Cataloging completed (success, failure, or cancel) |
| Test Rename String | Workbook exists + template entered |
| Build Renames | Workbook exists + template entered |
| Detect Duplicates | Workbook exists |
| Copy to Destination | Workbook exists + Destination Folder set |
| Move non-keepers | Workbook + Destination + dupes detected |
| Delete non-keepers | Workbook + Destination + dupes detected |
| Undo Last Operation | Workbook + Destination + rollback journal exists |

## Tips

- Always start with a Pre-Scan to verify folder contents before cataloging.
- The Destination Folder Layout preview updates in real time — use it to confirm your folder structure before copying.
- If you ran a catalog with Duplicate Detection set to "None," you can still detect duplicates afterward using the Detect Duplicates button without re-scanning.
- The Process Log captures detailed information about every operation. If something seems wrong, check the log first.
- Use "Move non-keepers" before "Delete non-keepers" if you want a chance to review duplicates before permanent deletion.
