# PhotoCatalog v3.0.0 — Design Notes

*Drafted 2026-04-15 during planning discussion. Captures the decisions that
drove the v3 build so the implementation can be read alongside the rationale.*

---

## 1. Purpose of v3

v2.1.x is a **cataloger + in-place renamer**: point it at one folder,
get back an Excel report, optionally write rename strings into the
`File_RenameName` column.

v3 extends the scope to **consolidate a messy photo drive into a clean,
date-organized destination**. The long-term goal is:

> Take a disorganized source drive of photos (possibly nested several
> levels deep, possibly accumulated from multiple phones / cameras /
> Lightroom exports), and reorganize the collection into a new
> destination with a clean year/month/day folder layout — with
> duplicates identified, grouped, and ready for the user to dispose of.

Because this is a meaningful scope change — new operations on the
filesystem beyond the source folder — v3 is a **major version bump**
(3.0.0), not a point release.

---

## 2. Summary of decisions

| Decision                     | Choice                                                                                |
|------------------------------|---------------------------------------------------------------------------------------|
| Default operation            | **Copy** (non-destructive). Move/Delete become follow-ups driven by the workbook.     |
| Source                       | Single source folder from the existing **Select Photo Folder** picker.                |
| Destination                  | New required **Destination Folder** picker.                                           |
| Rename filename template     | Existing free-form template (v2.1.1), now **persisted to JSON settings**.             |
| Folder layout                | **Checkbox-driven** (Year / Month / Day with per-level format choices).               |
| Duplicate detection          | Opt-in. Two modes: **Filename + File_SizeBytes** (fast) or **MD5 Hash** (thorough).   |
| Hash algorithm               | **MD5** (non-cryptographic, ~2–3× faster than SHA-256 on RAW files).                  |
| Duplicate keeper             | **Oldest `File_Date` wins**. User can override via `File_DupeKeep` column.            |
| Duplicate grouping           | `File_DupeGroup` integer ID. Rows sortable together.                                  |
| Duplicate highlight          | Distinct pale-orange fill on `File_Name` cell when `File_DupeGroup` is populated.     |
| Sidecars / pairs             | Treated as a unit. Same-stem / different-extension files in same folder move together.|
| Rollback                     | Per-run JSONL journal in the destination. **Undo Last Operation** button.             |
| Empty source folder cleanup  | Driven by the Excel file, logged, requires explicit confirmation.                      |
| Settings storage             | `%APPDATA%\PhotoCatalog\settings.json` (Windows-correct, survives upgrades).          |
| Persisted settings           | All UI selections: rename template, folder checkboxes, destination, dupe mode, etc.   |

---

## 3. New Excel columns (v3)

All use the existing `File_` prefix so they group with the other
app-generated / filesystem-sourced columns on the left side of the
Catalog sheet.

| Column            | Source                     | Notes                                                                  |
|-------------------|----------------------------|------------------------------------------------------------------------|
| `File_Hash`       | MD5 of file bytes          | Populated only when Hash dupe-detection mode is selected.              |
| `File_DupeGroup`  | Integer ID                 | Same ID = same duplicate group. Blank = not a duplicate.               |
| `File_DupeKeep`   | `TRUE` / `FALSE`           | `TRUE` for the auto-chosen keeper. User may edit before Move/Delete.   |
| `File_DestFolder` | Folder path string         | Rendered folder path under the destination root (from checkbox choice).|
| `File_DestPath`   | Full destination path      | `<DestFolder>\<File_RenameName>` — the copy target.                    |
| `File_Status`     | Enum string                | `Pending`, `Copied`, `Skipped`, `DupeMoved`, `DupeDeleted`, `Rollback`.|

`File_Name` cell is filled **pale orange (`FFFFD59B`)** when
`File_DupeGroup` is populated so duplicates read at a glance without
needing to sort by the group column.

---

## 4. Folder-layout checkboxes

The folder template is **not** a free-text string in v3 — it is a set
of three checkbox/radio pairs with a live preview. This sidesteps the
viability-checking complexity that would otherwise apply to a second
template and makes invalid folder paths structurally impossible.

```
┌─ Destination Folder Layout ─────────────────────────────────────┐
│ [x] Year folder   ( ) YY     (•) YYYY                           │
│ [x] Month folder  ( ) MM     (•) MM - MonthName  ( ) MonthName  │
│ [ ] Day folder    ( ) DD     ( ) YYYY-MM-DD                     │
│                                                                  │
│ Destination preview:  <dest>\2019\06 - June\IMG_0001.jpg         │
└──────────────────────────────────────────────────────────────────┘
```

Rules:

- Levels always compose in the order **Year → Month → Day** (no
  shuffling).
- Any unchecked level collapses; e.g. Year only → `<dest>\2019\IMG_0001.jpg`.
- If **all** levels are unchecked, files land flat in the destination root.
- Date fields used by the composer are sourced the same way the rename
  tokens do: `DateTimeOriginal` first, then `File_Date`, then (if both
  missing) the file is placed in a folder literally named `Unknown_Date`
  and flagged `[WARN]` in `File_Concern`.
- Path separators in the rendered folder are native Windows `\`.
  Characters illegal on Windows (`<>:"/\\|?*`) never appear in the
  rendered segments because the tokens only produce digits, month names,
  and hyphens — but the composer defensively scrubs anyway.

---

## 5. Duplicate detection

### Match modes

The user picks one of three in a combo box on the main window:

1. **None** — skip duplicate detection entirely. No hash computed.
2. **Filename + Size** — match on `(lowercase basename, File_SizeBytes)`.
   Fast, catches obvious cross-folder duplicates, rejects the "every
   camera starts at `IMG_0001`" false positive.
3. **MD5 Hash** — compute `File_Hash` for every file, then match on
   the hash. Thorough — catches renames and copies. Surfaces a warning
   dialog before starting so the user knows it'll roughly double the
   extract time on big RAW-heavy drives.

### Grouping and keeper selection

After detection, rows that share a match key get:

- The same integer in `File_DupeGroup` (groups numbered from 1).
- Exactly one row per group with `File_DupeKeep = TRUE` — the row
  with the **earliest `File_Date`**. Ties broken by shortest source
  path, then first encountered.
- All other rows in the group get `File_DupeKeep = FALSE`.

The user can open the workbook, sort/filter by `File_DupeGroup`,
review groups together (highlighted orange), and flip `TRUE` / `FALSE`
before kicking off a Move-non-keepers or Delete-non-keepers pass.

### Sidecar files and pairs

Duplicate detection operates on the **primary image file**. When a
file like `IMG_0001.NEF` is treated as a duplicate, its same-stem
sidecars in the same folder (`IMG_0001.JPG`, `IMG_0001.xmp`,
`IMG_0001.aae`, `IMG_0001.thm`, `IMG_0001.dop`) follow the primary to
its destination and share its duplicate fate. Sidecars are not
cataloged as independent rows in the workbook; they are detected at
copy/move time from the primary's folder.

---

## 6. Copy operation

`copy_engine.copy_row(row, rollback_writer)`:

1. Ensure `File_DestFolder` exists on disk (`os.makedirs(..., exist_ok=True)`).
2. Resolve the destination path. If a file already exists at
   `File_DestPath`, auto-suffix `_2`, `_3`, ... before the extension;
   log a `[WARN]` in `File_Concern` noting the suffix.
3. Detect sidecars next to the source (same stem, different extension
   from a built-in sidecar list).
4. `shutil.copy2` the primary to its destination. Copy each sidecar
   to the same destination folder using the same stem.
5. Write a rollback journal entry for the primary and each sidecar.
6. Mark `File_Status = Copied` (and write the (possibly suffixed)
   final path back into `File_DestPath`).

Rows with `File_DupeKeep = FALSE` **are still copied** by default in
the primary Copy pass — the Move/Delete passes run afterward on the
non-keepers specifically. This keeps "Copy" a single, predictable
operation that doesn't silently drop data; dedup disposition is
an explicit follow-up.

*(A user who wants to copy only keepers can filter the workbook before
the Copy pass — a future refinement might add a "Keepers only"
checkbox, but it isn't part of the v3.0.0 cut.)*

---

## 7. Rollback journal

Every destructive-ish operation (Copy, Move-non-keepers,
Delete-non-keepers) writes a JSONL file in the destination folder
named `_rollback_<YYYYMMDD_HHMMSS>.jsonl`. One line per file operation:

```json
{"ts": "2026-04-15T09:30:12", "op": "copy", "src": "C:\\Messy\\IMG_0001.jpg", "dst": "D:\\Clean\\2019\\06 - June\\IMG_0001.jpg"}
{"ts": "2026-04-15T09:30:12", "op": "copy", "src": "C:\\Messy\\IMG_0001.xmp", "dst": "D:\\Clean\\2019\\06 - June\\IMG_0001.xmp", "sidecar_of": "C:\\Messy\\IMG_0001.jpg"}
{"ts": "2026-04-15T09:31:02", "op": "delete", "src": "C:\\Messy\\IMG_0001.jpg"}
```

**Undo Last Operation** reads the newest journal in reverse and reverses
each entry:

- `copy` → delete the `dst`.
- `move` → move `dst` back to `src`.
- `delete` → cannot be auto-undone if the source is gone; entries
  are listed in the log with their original paths so the user can
  recover from backup.

Undo asks for a strong confirmation and writes a matching `_undo_…jsonl`
so the chain itself is auditable.

---

## 8. Empty source folder cleanup

After a Move-non-keepers or Delete-non-keepers pass, the tool offers
to walk the source tree once and list folders that are now empty.
The list is written to `_source_cleanup_candidates.log` in the
destination folder. A `Yes / No` dialog ("Remove N now-empty source
folders? See log.") surfaces the count; nothing is removed without
explicit confirmation. Removal itself is also journaled so the
rollback mechanism covers it.

---

## 9. Settings file

Path: `%APPDATA%\PhotoCatalog\settings.json` (same file the v2.x
`settings.py` already creates).

New keys added in v3:

```json
{
  "destination_folder": "D:\\Clean",
  "rename_template": "%Date_YYYY%-%Date_MM%-%Date_DD%_%File_Name%%File_Extension%",
  "folder_level_year": true,
  "folder_format_year": "YYYY",
  "folder_level_month": true,
  "folder_format_month": "MM - MonthName",
  "folder_level_day": false,
  "folder_format_day": "DD",
  "dupe_mode": "filename_size",
  "operation_default": "copy"
}
```

All v2.x keys continue to load. Unknown future keys survive round-trips
(the loader only filters unknown keys on read, not on write).

---

## 10. UI changes

The main window grows a **Destination Folder** row below *Save Report
to Folder*, a **Destination Folder Layout** block (checkboxes + preview)
below the Rename section, and a new button row:

```
[ Copy to Destination ]  [ Move non-keepers... ]  [ Delete non-keepers ]  [ Undo Last ]
```

Buttons gate on:

- *Copy to Destination* — catalog workbook exists AND `File_DestPath`
  is populated on at least one row.
- *Move non-keepers / Delete non-keepers* — a prior Copy pass has
  populated `File_Status = Copied` on at least one row.
- *Undo Last* — a `_rollback_*.jsonl` file exists in the destination.

All destructive buttons (Move, Delete, Undo) require a
`QMessageBox.question` confirmation that names the operation, the
file count, and the destination.

---

## 11. Module layout after v3

```
scripts/
  catalog_pipeline.py      (extended)
  config.py                (extended COLUMN_ORDER)
  copy_engine.py           (NEW — copy pass + rollback journal writer)
  duplicate_detector.py    (NEW — hash + filename modes, group/keeper)
  folder_composer.py       (NEW — checkbox → folder path)
  gui_main.py              (extended)
  photo_catalog.py         (extended — optional MD5, new concern checks)
  rename_engine.py         (minor tweaks)
  rollback.py              (NEW — JSONL reader + undo)
  settings.py              (extended default keys)
  run_gui.py               (unchanged)
  run_catalog.py           (extended CLI flags)
```

---

## 12. Out of scope for v3.0.0

Called out so they don't creep in:

- Copying only keepers in the main Copy pass (use Delete-non-keepers
  afterward if that's the desired outcome).
- Multi-source-root runs (single source folder as per decision table).
- Cloud destinations (OneDrive/Drive/SMB). Local filesystem only.
- Re-detecting duplicates on an existing workbook without a re-scan.
- Automated integrity verification (hash of source vs. destination
  after copy). Possible v3.1 addition.
- Partial rollback (undo a subset of a run). All-or-nothing per journal.

---

*End of design notes. Implementation follows this document; any
intentional deviation should be reflected back here and in the
CHANGELOG.*
