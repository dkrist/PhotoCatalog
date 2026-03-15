#!/usr/bin/env python3
"""
Quick-run wrapper — catalogs photos in the inbox folder by default,
or any folder passed as an argument. Output goes to the output/ folder.
 
If no folder is specified on the command line, a GUI folder picker dialog
will open so you can select the folder interactively.
 
Usage:
    python run_catalog.py                  # GUI folder picker, with face recognition
    python run_catalog.py /path/to/photos  # Scan specific folder
    python run_catalog.py --no-faces       # GUI picker, skip face recognition
    python run_catalog.py /path --no-faces # Both options
"""
import os
import sys
 
# Add scripts dir to path so we can import photo_catalog
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
from photo_catalog import scan_folder, extract_metadata, write_excel
from datetime import datetime
 
 
def pick_folder_gui():
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
            mustexist=True
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
 
 
def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inbox = os.path.join(project_root, 'inbox')
    output_dir = os.path.join(project_root, 'output')
 
    enable_faces = '--no-faces' not in sys.argv
    folder = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            folder = arg
 
    # If no folder was passed on the command line, open the GUI picker
    if not folder:
        print("No folder specified — opening folder picker...")
        folder = pick_folder_gui()
        if not folder:
            print("No folder selected. Exiting.")
            sys.exit(0)
 
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
