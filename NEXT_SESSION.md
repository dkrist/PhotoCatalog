# PhotoCatalog v3.0.0 — Session Handoff (2026-04-16)

## Where we left off

All v3 features are coded, compiling, and passing initial testing. The user ran a first round of tests with doctored files (forced size-collisions and hash-matches) — results looked good. More thorough testing planned for tonight.

## What needs to be committed before tagging v3.0.0

- `README.md` — updated with the new **Smart Hash Strategy** section (crediting Claude).
- Several other modified files show in `git status` (documentation, `.gitignore`, legacy scripts like `photo_catalog.py`, `config.py`, `face_recognition.py`, `requirements.txt`). The user should review which of these belong in the v3 tag commit.

## What's been tested

- Cataloging a real 1,305-row workbook: scanning, metadata, duplicate detection (filename+size and MD5 hash modes) all producing correct results (385 groups, 770 rows in groups, orange fill, keeper selection).
- Smart-hash optimization: first round passed on doctored test set. Candidate selection logic unit-tested (size_collision_candidates returns correct paths for collision/unique/invalid rows).
- "Detect Duplicates on Existing Workbook" button: working on real data.
- UI layout: combo moved next to Detect Dupes button, progress bar folded into log header row.

## What has NOT been tested yet

- Cancel mid-hash with smart-hash optimization active (candidate-count progress vs row-count progress).
- Smart-hash toggle parity: running the same workbook with "Hash all files" on vs off and diffing `File_DupeGroup`/`File_DupeKeep` (should be identical; `File_Hash` will differ only on size-unique rows).
- Edge case: two files same size, different content (should be hashed, not grouped).
- Copy/Move/Delete destination workflows on a large (50k+) library.
- Undo/rollback after Move or Delete.

## Key architecture notes for the next session

- **Smart-hash optimization** lives in `duplicate_detector.size_collision_candidates()` and the `candidate_paths` parameter on `populate_hashes()`. The opt-out flag (`always_hash_all_files`) threads from `settings.py` through `gui_main.py` (checkbox) to both `CatalogWorker` and `DetectDupesWorker`, then into `catalog_pipeline.run_catalog()` and `duplicate_detector.detect_duplicates_on_workbook()`.
- **Progress adapter shim**: `_ProgressFormatProxy` in `gui_main.py` routes all `progress_counter.setText()` calls to `QProgressBar.setFormat()` so the bar doubles as the status label. Saves vertical space without rewriting 20+ call sites.
- **Settings**: `settings.json` in `%APPDATA%\PhotoCatalog\`. New v3 keys include `destination_folder`, `folder_level_*`, `folder_format_*`, `dupe_mode`, `always_hash_all_files`, `operation_default`.

## Possible next steps (user's call)

- Finish testing, commit, tag `v3.0.0`, push.
- Update the app screenshot in the repo to reflect the current v3 UI.
- Consider adding a "last used workbook" persistence so `last_report_path` survives app restarts (currently resets to None on launch).
