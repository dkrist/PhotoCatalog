"""
catalog_pipeline.py — Reusable cataloging pipeline shared by the CLI
(run_catalog.py) and the GUI (gui_main.py).

The pipeline runs three phases:
  1. Scan the folder and extract EXIF/XMP metadata for every supported image.
  2. (Optional) Run face recognition and attach person names.
  3. Write a formatted Excel workbook to the output folder.

The `run_catalog` function accepts callbacks so callers can surface progress
and log messages however they like (print, logging, Qt signals, etc.) and
an optional cancel flag so the GUI can request an early exit between
files without killing the process.
"""
import os
import threading
from datetime import datetime
from typing import Callable, Dict, Optional, Tuple

from photo_catalog import (
    extract_metadata,
    prescan_folder as _engine_prescan,
    scan_folder,
    write_excel,
)

# --- v3 modules --------------------------------------------------------------
# These are optional phases in the pipeline; they only run when the GUI / CLI
# passes in the matching parameters. Keeping the imports at module scope means
# the pipeline fails loud at import time if the supporting modules disappear
# during packaging, rather than raising mid-run on the first file.
from duplicate_detector import (
    detect_duplicates,
    populate_hashes,
    size_collision_candidates,
)
from folder_composer import FolderConfig
from copy_engine import populate_destination_columns


# Typed aliases for clarity on the callback signatures.
ProgressCallback = Callable[[int, int, str], None]   # (current, total, message)
LogCallback = Callable[[str], None]                   # (text) -> None
PrescanProgressCallback = Callable[[int, int], None]  # (files_seen, folders_seen)


class CatalogCancelled(Exception):
    """Raised internally when the caller requests cancellation."""


def _noop_progress(current: int, total: int, message: str) -> None:
    pass


def _noop_log(message: str) -> None:
    pass


def _check_cancel(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise CatalogCancelled()


# ---------------------------------------------------------------------------
# Output path helpers — filename construction, collision handling, locks
# ---------------------------------------------------------------------------
# These are exposed publicly so the GUI can do a pre-flight check before
# launching the (potentially long-running) pipeline.

def default_output_filename(folder: str, today: Optional[str] = None) -> str:
    """Build the default `PhotoCatalog_<FolderName>_<YYYY-MM-DD>.xlsx` filename."""
    folder_name = os.path.basename(os.path.abspath(folder))
    today = today or datetime.now().strftime('%Y-%m-%d')
    return f"PhotoCatalog_{folder_name}_{today}.xlsx"


def default_output_path(folder: str, output_dir: str) -> str:
    """Full path for the default output file (directory + default filename)."""
    return os.path.join(output_dir, default_output_filename(folder))


def find_available_path(base_path: str) -> str:
    """
    Return `base_path` if unused, otherwise append `_2`, `_3`, ... before
    the extension until a free name is found.

    Example:
      report.xlsx             -> report.xlsx       (if not present)
      report.xlsx exists      -> report_2.xlsx     (if not present)
      report.xlsx + _2 exist  -> report_3.xlsx     (and so on)
    """
    if not os.path.exists(base_path):
        return base_path
    stem, ext = os.path.splitext(base_path)
    n = 2
    while True:
        candidate = f"{stem}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def is_file_locked(path: str) -> bool:
    """
    Return True if `path` exists and is currently locked for writing.

    On Windows, files open in Excel/Word are locked exclusively, so attempting
    to open them for read+write raises PermissionError. We detect that here
    without modifying the file. Missing files are not considered locked.
    """
    if not os.path.exists(path):
        return False
    try:
        # r+b opens for read+write without truncating. If another process
        # holds an exclusive lock (e.g. Excel on Windows), this raises.
        with open(path, 'r+b'):
            return False
    except PermissionError:
        return True
    except OSError:
        # Other I/O errors — treat as locked to be safe.
        return True


def run_prescan(
    folder: str,
    progress_callback: Optional[PrescanProgressCallback] = None,
    log_callback: Optional[LogCallback] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Dict:
    """
    Run an informational pre-scan of ``folder`` and log a summary.

    This is a thin wrapper over ``photo_catalog.prescan_folder`` that
    adds nicely-formatted log output so callers (GUI, CLI) can print
    the same report. Returns the raw result dict for further inspection.

    Args:
        folder: Path to the folder tree to pre-scan.
        progress_callback: Called periodically during the walk with
            ``(files_seen, folders_seen)``. Passed through unchanged.
        log_callback: Receives human-readable status messages — the
            formatted report is delivered via this callback.
        cancel_event: If set partway through, the walk returns early.

    Returns:
        The dict produced by ``prescan_folder`` plus a ``formatted_report``
        string suitable for writing to a log file.

    Raises:
        FileNotFoundError: folder does not exist.
    """
    log = log_callback or _noop_log

    if not os.path.isdir(folder):
        raise FileNotFoundError(f"'{folder}' is not a valid directory.")

    log(f"=== Pre-scan: {folder} ===")
    result = _engine_prescan(
        folder,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
    )

    # Build the formatted report that mirrors the CR spec.
    lines = [f"=== Pre-scan: {folder} ==="]
    if result["cancelled"]:
        lines.append("(cancelled by user — counts below are partial)")
    lines.append(f"Folders scanned: {result['total_folders']:>10,}")
    lines.append(f"Total files:     {result['total_files']:>10,}")
    lines.append(f"Supported images:{result['supported_count']:>10,}")
    for ext, count in result["supported_by_ext"].most_common():
        lines.append(f"  {ext:<8} {count:>8,}")
    lines.append(f"Other files:     {result['other_count']:>10,}")
    for ext, count in result["other_by_ext"].most_common(15):
        lines.append(f"  {ext:<8} {count:>8,}")
    extra = len(result["other_by_ext"]) - 15
    if extra > 0:
        lines.append(f"  (+{extra} more extension{'s' if extra != 1 else ''})")
    report = "\n".join(lines)

    # Stream each line to the callback so it appears progressively in
    # the log panel rather than as one big blob.
    for line in lines[1:]:
        log(line)

    result["formatted_report"] = report
    return result


def run_catalog(
    folder: str,
    output_dir: str,
    enable_faces: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
    log_callback: Optional[LogCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    output_path: Optional[str] = None,
    dupe_mode: str = "none",
    folder_config: Optional[FolderConfig] = None,
    destination_folder: Optional[str] = None,
    rename_template: str = "",
    always_hash_all_files: bool = False,
) -> Tuple[str, int, int]:
    """
    Run the full PhotoCatalog pipeline end-to-end.

    Args:
        folder: Photo folder to scan (recursive).
        output_dir: Folder where the Excel report is written.
        enable_faces: Whether to run face recognition phase.
        progress_callback: Receives (current, total, message) updates.
        log_callback:     Receives human-readable status messages.
        cancel_event:     If set, the pipeline exits between files.
        output_path:      Optional full path for the Excel file. If omitted,
                          the default PhotoCatalog_<Folder>_<date>.xlsx name
                          in `output_dir` is used. Callers (e.g. the GUI)
                          can pass a versioned path like `..._2.xlsx` when
                          the default one is locked.
        dupe_mode:        v3 duplicate detection mode. One of
                          ``"none"``, ``"filename_size"``, ``"hash"``.
                          ``"hash"`` triggers an extra MD5 pass over every
                          file before detection runs.
        folder_config:    v3 :class:`folder_composer.FolderConfig` describing
                          the destination folder layout. If supplied together
                          with *destination_folder*, the pipeline populates
                          the File_DestFolder / File_DestPath / File_Status
                          columns so the workbook is immediately usable as
                          input to the Copy pass.
        destination_folder: v3 destination root for the Copy pass.
                          Only used when *folder_config* is also provided.
        rename_template:  v3 rename filename template (free-form
                          ``%Variable%`` string). Empty string means "keep
                          original filename".
        always_hash_all_files: If ``True`` and ``dupe_mode == "hash"``,
                          compute MD5 for every file regardless of
                          whether its size collides with another. The
                          default ``False`` enables the smart-hash
                          optimization that skips size-unique rows
                          (typically 80–95% of a real library) since
                          they cannot have a byte-identical twin.

    Returns:
        (output_path, num_rows, num_cols) on success.

    Raises:
        FileNotFoundError: folder does not exist.
        ValueError:        no supported files in folder.
        CatalogCancelled:  cancel_event was set mid-run.
    """
    progress = progress_callback or _noop_progress
    log = log_callback or _noop_log

    if not os.path.isdir(folder):
        raise FileNotFoundError(f"'{folder}' is not a valid directory.")

    os.makedirs(output_dir, exist_ok=True)

    folder_name = os.path.basename(os.path.abspath(folder))
    if output_path is None:
        output_path = default_output_path(folder, output_dir)

    # --- Scan ------------------------------------------------------------
    log(f"Scanning: {folder}")
    files = scan_folder(folder)
    if not files:
        raise ValueError("No supported image files found.")
    total = len(files)
    log(f"Found {total} supported image files")

    # --- Phase 1: Metadata ----------------------------------------------
    log("--- Phase 1: Extracting metadata ---")
    all_rows = []
    for i, filepath in enumerate(files, start=1):
        _check_cancel(cancel_event)
        all_rows.append(extract_metadata(filepath))
        # Emit progress every file so the GUI bar moves smoothly.
        progress(i, total, os.path.basename(filepath))
        if i == 1 or i % 50 == 0 or i == total:
            log(f"  Processed {i}/{total}: {os.path.basename(filepath)}")

    # --- Phase 2: Faces --------------------------------------------------
    if enable_faces:
        log("--- Phase 2: Face recognition ---")
        try:
            from face_recognition import process_all_faces

            def _face_progress(current: int, total_: int, name: str) -> None:
                _check_cancel(cancel_event)
                log(f"  Detecting faces {current}/{total_}: {name}")

            face_results = process_all_faces(files, progress_callback=_face_progress)

            for i, filepath in enumerate(files):
                result = face_results.get(filepath, {})
                all_rows[i]['FaceCount_Detected'] = result.get('face_count', 0)
                all_rows[i]['PersonNames'] = result.get('person_names', '')

            total_faces = sum(r.get('face_count', 0) for r in face_results.values())
            photos_with_faces = sum(1 for r in face_results.values() if r.get('face_count', 0) > 0)
            all_persons = set()
            for r in face_results.values():
                names = r.get('person_names', '')
                if names:
                    for p in names.split(', '):
                        all_persons.add(p.strip())
            log(f"  Found {total_faces} faces in {photos_with_faces} photos")
            log(f"  Identified {len(all_persons)} unique persons")
        except ImportError:
            log("  face_recognition module not found — skipping")
        except CatalogCancelled:
            raise
        except Exception as e:
            log(f"  Face recognition failed: {e}")
    else:
        log("--- Phase 2: Face recognition skipped ---")

    # --- v3 Phase 2b: MD5 hashing (only when dupe_mode == "hash") --------
    # Hashing is the slowest optional step — a full RAW drive can take
    # many minutes — so it's gated behind the dupe-mode selector. The
    # filename+size mode doesn't need hashes at all, and the "none" mode
    # obviously skips this phase too.
    if dupe_mode == "hash":
        _check_cancel(cancel_event)
        log("--- Phase 2b: Hashing files (MD5) ---")

        # Smart-hash optimization: only hash files whose size collides
        # with another row's size. Two byte-identical files MUST share
        # a size, so size-unique files cannot have a duplicate twin and
        # are guaranteed safe to skip. Caller can opt out via
        # always_hash_all_files=True for a fully populated File_Hash
        # column. See README "Smart Hash Strategy" for the math.
        if always_hash_all_files:
            log("  Smart-hash optimization disabled — full sweep over all files.")
            candidate_set = None
        else:
            candidate_set = size_collision_candidates(all_rows)
            total_rows = len(all_rows)
            planned = len(candidate_set)
            skipped = total_rows - planned
            pct = (100.0 * skipped / total_rows) if total_rows else 0
            log(
                f"  Smart-hash optimization: hashing {planned:,} of "
                f"{total_rows:,} files ({skipped:,} unique-size rows "
                f"skipped, {pct:.1f}% I/O saved)."
            )

        def _hash_progress(current: int, total_: int) -> None:
            _check_cancel(cancel_event)
            progress(current, total_, "hashing")
            if current == 1 or current % 100 == 0 or current == total_:
                log(f"  Hashed {current}/{total_}")

        hashed = populate_hashes(
            all_rows,
            progress_callback=_hash_progress,
            cancel_event=cancel_event,
            candidate_paths=candidate_set,
        )
        log(f"  Hashed {hashed} file(s)")

    # --- v3 Phase 2c: Duplicate detection --------------------------------
    if dupe_mode and dupe_mode != "none":
        _check_cancel(cancel_event)
        log(f"--- Phase 2c: Duplicate detection ({dupe_mode}) ---")
        dupe_summary = detect_duplicates(all_rows, mode=dupe_mode)
        log(
            f"  {dupe_summary['groups']} group(s), "
            f"{dupe_summary['duplicate_rows']} row(s) in groups, "
            f"{dupe_summary['keepers']} keeper(s), "
            f"{dupe_summary['non_keepers']} non-keeper(s), "
            f"{dupe_summary['skipped']} skipped (no match key)."
        )

    # --- v3 Phase 2d: Destination-column composition ---------------------
    # Populates File_RenameName / File_DestFolder / File_DestPath /
    # File_Status from the folder_config + rename_template. This means
    # the workbook that lands on disk already has everything the Copy
    # button needs — no second pass required to pre-render destinations.
    if folder_config is not None and destination_folder:
        _check_cancel(cancel_event)
        log("--- Phase 2d: Composing destination paths ---")
        dest_summary = populate_destination_columns(
            all_rows,
            destination_root=destination_folder,
            folder_config=folder_config,
            rename_template=rename_template,
        )
        log(
            f"  {dest_summary['resolved']} resolved, "
            f"{dest_summary['unknown_date']} to Unknown_Date, "
            f"{dest_summary['rename_fallback']} rename fallbacks, "
            f"{dest_summary['dupe_fallback_date']} File_Date fallbacks."
        )

    # --- Phase 3: Excel --------------------------------------------------
    _check_cancel(cancel_event)
    log("--- Phase 3: Writing Excel ---")
    log(f"Output: {output_path}")
    num_cols, num_rows, concern_totals = write_excel(all_rows, output_path, folder_name)
    log(f"Done! {num_rows} photos x {num_cols} columns")

    # CR #1 summary line: one-line tally of File_Concern markers across
    # the whole run so the user can see at a glance whether any rows
    # were flagged (and whether any of them are [ERROR] rows that will
    # block a future rename/move pass).
    if concern_totals.get('rows_with_concerns'):
        log(
            f"File_Concern markers: [INFO] {concern_totals['info']:,}, "
            f"[WARN] {concern_totals['warn']:,}, "
            f"[ERROR] {concern_totals['error']:,} "
            f"across {concern_totals['rows_with_concerns']:,} row(s)"
        )
    else:
        log("File_Concern: no issues flagged.")

    return output_path, num_rows, num_cols
