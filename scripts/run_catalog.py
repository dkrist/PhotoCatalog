#!/usr/bin/env python3
"""
Quick-run wrapper — catalogs photos in the inbox folder by default,
or any folder passed as an argument. Output goes to the output/ folder.

Usage:
    python run_catalog.py                     # Scan inbox/, with face recognition
    python run_catalog.py /path/to/photos     # Scan specific folder
    python run_catalog.py --no-faces          # Skip face recognition
    python run_catalog.py /path --no-faces    # Both options
"""
import os
import sys

# Add scripts dir to path so we can import photo_catalog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from photo_catalog import scan_folder, extract_metadata, write_excel
from datetime import datetime


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inbox = os.path.join(project_root, 'inbox')
    output_dir = os.path.join(project_root, 'output')

    enable_faces = '--no-faces' not in sys.argv
    folder = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            folder = arg
    if not folder:
        folder = inbox

    folder_name = os.path.basename(os.path.abspath(folder))

    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)

    today = datetime.now().strftime('%Y-%m-%d')
    output_path = os.path.join(output_dir, f"PhotoCatalog_{folder_name}_{today}.xlsx")

    print(f"Scanning: {folder}")
    files = scan_folder(folder)

    if not files:
        print("No supported image files found.")
        sys.exit(0)

    print(f"Found {len(files)} supported image files")

    # Phase 1: Extract metadata
    print("\n--- Phase 1: Extracting metadata ---")
    all_rows = []
    for i, filepath in enumerate(files):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Processing {i + 1}/{len(files)}: {os.path.basename(filepath)}")
        all_rows.append(extract_metadata(filepath))

    # Phase 2: Face recognition
    if enable_faces:
        print("\n--- Phase 2: Face recognition ---")
        try:
            from face_recognition import process_all_faces

            def progress(current, total, name):
                print(f"  Detecting faces {current}/{total}: {name}")

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
            print(f"  Found {total_faces} faces in {photos_with_faces} photos")
            print(f"  Identified {len(all_persons)} unique persons")
        except ImportError:
            print("  Warning: face_recognition module not found, skipping")
        except Exception as e:
            print(f"  Warning: Face recognition failed: {e}")
    else:
        print("\n--- Phase 2: Face recognition skipped (--no-faces) ---")

    # Phase 3: Write Excel
    print(f"\n--- Phase 3: Writing Excel ---")
    print(f"Output: {output_path}")
    num_cols, num_rows = write_excel(all_rows, output_path, folder_name)
    print(f"Done! {num_rows} photos x {num_cols} columns")


if __name__ == '__main__':
    main()
