#!/usr/bin/env python3
"""
run_gui.py — Launch the PhotoCatalog desktop UI.

Usage:
    python run_gui.py

This is a thin wrapper around gui_main.main() so the GUI has the same
entry-point feel as run_catalog.py does for the CLI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui_main import main

if __name__ == "__main__":
    sys.exit(main())
