#!/usr/bin/env python3
"""
Quick-run wrapper — catalogs photos in the inbox folder by default,
or any folder passed as an argument. Output goes to the folder configured
via the `save_report_to` user setting (see settings.py).

If no folder is specified on the command line, a GUI folder picker dialog
will open so you can select the folder interactively.

Usage:
    python run_catalog.py                  # GUI folder picker, with face recognition
    python run_catalog.py /path/to/photos  # Scan specific folder
    python run_catalog.py --no-faces       # GUI picker, skip face recognition
    python run_catalog.py /path --no-faces # Both options
    python run_catalog.py --show-settings  # Print current settings and exit
"""
import logging
import os
import sys
from datetime import datetime

# Add scripts dir to path so we can import sibling modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from photo_catalog import scan_folder, extract_metadata, write_excel
from settings import get_settings


def pick_folder_gui(initial_dir: str = ""):
    """Open a tkinter folder picker dialog and return the selected path, or None."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        # Create a root window and hide it
        root = tk.Tk()
        root.withdraw()

        # Bring the dialog to the front
        root.attributes('-topmost', True)

        folder = filedialog.askdirectory(
            title="Select Photo Folder to Catalog",
            mustexist=True,
            initialdir=initial_dir or os.path.expanduser("~"),
        )

        root.destroy()

        if folder:
            return folder
        else:
            return None
    except ImportError:
        print("Warning: tkinter not available. Please pass a folder path as an argument.")
        return None
    except Exception as e:
        print(f"Warning: Could not open folder picker: {e}")
        return None


def configure_logging(log_dir: str, log_level: str) -> str:
    """Configure root logger to write to a timestamped file in log_dir.

    Returns the log file path so the caller can report it.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir, f"photocatalog_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.log"
    )

    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def main():
    # Load user settings (creates %APPDATA%\PhotoCatalog\config.json on first run).
    settings = get_settings()

    # Handle --show-settings convenience flag.
    if '--show-settings' in sys.argv:
        import json
        print(f"Config file: {settings.config_path}")
        print(json.dumps(settings.all(), indent=2))
        sys.exit(0)

    # Resolve configured folders and ensure they exist.
    output_dir = str(settings.ensure_folder("save_report_to"))
    log_dir = str(settings.ensure_folder("log_file_folder"))

    # Set up file + console logging BEFORE doing any real work.
    log_file = configure_logging(log_dir, settings.get("log_level", "INFO"))
    log = logging.getLogger("run_catalog")
    log.info("PhotoCatalog starting — log file: %s", log_file)
    log.info("Reports will be saved to: %s", output_dir)

    # Parse CLI args (simple scheme — preserves previous behavior).
    # --no-faces overrides the user's enable_face_recognition setting.
    enable_faces = settings.get("enable_face_recognition", True)
    if '--no-faces' in sys.argv:
        enable_faces = False

    folder = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            folder = arg

    # If no folder was passed on the command line, open the GUI picker.
    # Seed it with the user's last-used folder when available.
    if not folder:
        log.info("No folder specified — opening folder picker...")
        initial = settings.get("default_scan_folder") or ""
        folder = pick_folder_gui(initial_dir=initial)
        if not folder:
            log.info("No folder selected. Exiting.")
            sys.exit(0)

    folder_name = os.path.basename(os.path.abspath(folder))

    if not os.path.isdir(folder):
        log.error("'%s' is not a valid directory.", folder)
        sys.exit(1)

    # Remember this folder for next time.
    settings.set("default_scan_folder", os.path.abspath(folder))
    settings.add_recent_folder(os.path.abspath(folder))
    settings.save()

    today = datetime.now().strftime('%Y-%m-%d')
    output_path = os.path.join(output_dir, f"PhotoCatalog_{folder_name}_{today}.xlsx")

    log.info("Scanning: %s", folder)
    files = scan_folder(folder)

    if not files:
        log.warning("No supported image files found.")
        sys.exit(0)

    log.info("Found %d supported image files", len(files))

    # Phase 1: Extract metadata
    log.info("--- Phase 1: Extracting metadata ---")
    all_rows = []
    for i, filepath in enumerate(files):
        if (i + 1) % 50 == 0 or i == 0:
            log.info("  Processing %d/%d: %s", i + 1, len(files), os.path.basename(filepath))
        all_rows.append(extract_metadata(filepath))

    # Phase 2: Face recognition
    if enable_faces:
        log.info("--- Phase 2: Face recognition ---")
        try:
            from face_recognition import process_all_faces

            def progress(current, total, name):
                log.info("  Detecting faces %d/%d: %s", current, total, name)

            face_results = process_all_faces(files, progress_callback=progress)

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
            log.info("  Found %d faces in %d photos", total_faces, photos_with_faces)
            log.info("  Identified %d unique persons", len(all_persons))
        except ImportError:
            log.warning("  face_recognition module not found, skipping")
        except Exception as e:
            log.warning("  Face recognition failed: %s", e)
    else:
        log.info("--- Phase 2: Face recognition skipped (--no-faces or setting disabled) ---")

    # Phase 3: Write Excel
    log.info("--- Phase 3: Writing Excel ---")
    log.info("Output: %s", output_path)
    num_cols, num_rows = write_excel(all_rows, output_path, folder_name)
    log.info("Done! %d photos x %d columns", num_rows, num_cols)


if __name__ == '__main__':
    main()
