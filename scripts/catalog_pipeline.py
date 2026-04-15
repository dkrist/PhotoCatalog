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
