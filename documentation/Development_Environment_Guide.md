# PhotoCatalog Development Environment Guide

**David Krist | March 2026 | Version 1.0**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Development Tools](#2-development-tools)
3. [Python Libraries](#3-python-libraries)
4. [Project Structure](#4-project-structure)
5. [Workflow Diagram](#5-workflow-diagram)
6. [Common Git Workflow](#6-common-git-workflow)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Overview

PhotoCatalog is a Python-based batch application that scans folders of photos, extracts EXIF and XMP metadata from each image, and produces a formatted Excel spreadsheet with one row per photo. The application also includes optional face recognition capabilities and a graphical folder picker for ease of use.

This document describes each software tool and library used in the PhotoCatalog development environment, explains how they interact, and provides a visual workflow diagram showing the complete development and execution pipeline.

---

## 2. Development Tools

### 2.1 Visual Studio Code (VS Code)

Visual Studio Code is a free, open-source code editor developed by Microsoft. It serves as the primary Integrated Development Environment (IDE) for the PhotoCatalog project.

**Role in the project:** VS Code is where all source code is written, edited, and debugged. It provides syntax highlighting for Python, an integrated terminal for running scripts and Git commands, and built-in Git integration for viewing changes and managing commits.

**Key features used:** The integrated terminal (accessed via Ctrl+backtick) is used extensively for running Python scripts, Git commands, and pip installs. The Python extension provides IntelliSense, linting, and debugging support.

**Website:** https://code.visualstudio.com/

### 2.2 Python

Python is a high-level, general-purpose programming language known for its readability and extensive library ecosystem. PhotoCatalog is written entirely in Python.

**Role in the project:** Python is the runtime that executes all PhotoCatalog scripts. The project uses Python 3.x and leverages several third-party libraries (Pillow, openpyxl) as well as standard library modules (tkinter, os, sys, datetime, xml).

**Key commands:**

| Command | Purpose |
|---------|---------|
| `python scripts/run_catalog.py` | Run the catalog with GUI folder picker |
| `python scripts/run_catalog.py /path` | Run on a specific folder |
| `python scripts/run_catalog.py --no-faces` | Run without face recognition |

**Website:** https://www.python.org/

### 2.3 Git

Git is a distributed version control system that tracks changes to source code over time. It allows developers to maintain a complete history of every change made to a project, create branches for experimental features, and collaborate with others.

**Role in the project:** Git runs locally on your machine and tracks every change to the PhotoCatalog source files. When you edit a file and commit it, Git creates a snapshot of the project at that point in time. This means you can always go back to a previous version if something breaks.

**Key concepts:**

| Concept | Description |
|---------|-------------|
| Repository (repo) | The project folder tracked by Git, including all history |
| Commit | A saved snapshot of your changes with a descriptive message |
| Branch | An independent line of development (main is the default branch) |
| Push | Upload local commits to the remote repository (GitHub) |
| Pull | Download changes from the remote repository to your local machine |

**Current version:** Git 2.53.0 (installed on your Windows machine)

**Website:** https://git-scm.com/

### 2.4 GitHub

GitHub is a cloud-based platform that hosts Git repositories and provides collaboration features such as pull requests, issue tracking, code review, and project management tools.

**Role in the project:** GitHub stores the remote copy of the PhotoCatalog repository. When you push commits from your local machine, they are uploaded to GitHub. This serves as a backup, a portfolio piece, and a collaboration platform if you ever work with others on the project. The PhotoCatalog repo is currently set to Private.

**Your repository:** https://github.com/dkrist/PhotoCatalog

**Website:** https://github.com/

### 2.5 GitHub CLI (gh)

The GitHub CLI is a command-line tool that brings GitHub functionality directly into your terminal.

**Role in the project:** The GitHub CLI was used to authenticate your local machine with your GitHub account (via `gh auth login`). It can also be used to create repositories, open pull requests, and manage issues without leaving VS Code's terminal.

**Key commands:**

| Command | Purpose |
|---------|---------|
| `gh auth login` | Authenticate with GitHub via browser |
| `gh repo create` | Create a new repository on GitHub |
| `gh repo view --web` | Open the repo in your browser |
| `gh pr create` | Create a pull request from the terminal |

**Current version:** gh 2.88.1

**Website:** https://cli.github.com/

---

## 3. Python Libraries

The following Python libraries are used by PhotoCatalog at runtime. They are installed via pip and listed in the project's requirements.txt file.

### 3.1 Pillow (PIL)

Pillow is the modern fork of the Python Imaging Library (PIL). It provides extensive image processing capabilities and is the most widely used Python library for working with image files.

**Role in the project:** Pillow opens each photo file and reads its embedded EXIF metadata, which includes camera make/model, date taken, GPS coordinates, exposure settings, lens information, and more. It supports all major image formats including JPEG, TIFF, PNG, HEIF, and various RAW formats.

**Install command:** `pip install Pillow`

**Website:** https://pillow.readthedocs.io/

### 3.2 openpyxl

openpyxl is a Python library for reading and writing Excel 2010+ (.xlsx) files. It supports formulas, charts, styling, conditional formatting, and all standard Excel features.

**Role in the project:** openpyxl creates the final Excel output file. It builds the Catalog sheet (one row per photo with all metadata columns) and the Summary sheet (statistics about the photo collection). It also handles formatting such as header styling, alternating row colors, column auto-fit, frozen headers, auto-filters, and proper date formatting.

**Install command:** `pip install openpyxl`

**Website:** https://openpyxl.readthedocs.io/

### 3.3 tkinter

tkinter is Python's standard GUI (Graphical User Interface) toolkit. It comes bundled with most Python installations and provides dialog boxes, windows, buttons, and other UI elements.

**Role in the project:** tkinter provides the folder picker dialog that appears when you run the script without specifying a folder path on the command line. It opens a native Windows browse dialog where you can navigate to and select the photo folder you want to catalog. This was added as a Phase 2 enhancement to improve usability.

**Install command:** None needed (included with Python)

### 3.4 face_recognition (Optional)

The face_recognition module is an optional component that uses machine learning to detect and identify faces in photos. It is not required for the core cataloging functionality.

**Role in the project:** When enabled, the face recognition module scans each photo for faces, counts how many are detected, and attempts to match them against known persons. The results are added as additional columns in the Excel output (FaceCount_Detected and PersonNames). It can be disabled with the `--no-faces` flag.

**Note:** This module requires additional dependencies (dlib, face_recognition) that can be complex to install. The script handles missing dependencies gracefully and will skip face recognition if the module is not available.

---

## 4. Project Structure

```
PhotoCatalog/                    # Project root (Git repository)
├── scripts/                     # Python source code
│   ├── run_catalog.py           # Entry point with folder picker and orchestration
│   ├── photo_catalog.py         # Core logic: metadata extraction, Excel writing
│   ├── config.py                # Configuration: file types, column order, constants
│   └── face_recognition.py      # Optional face detection module
├── documentation/               # Project documentation
├── output/                      # Generated Excel catalog files
├── .gitignore                   # Files excluded from version control
└── requirements.txt             # Python package dependencies
```

---

## 5. Workflow Diagram

### Development Workflow

```
┌──────────┐  edits code  ┌──────────────┐   commit    ┌───────────┐
│Developer │ ────────────► │   VS Code    │ ──────────► │    Git    │
│ (David)  │               │ IDE / Editor │              │  Local VC │
└──────────┘               └──────────────┘              └─────┬─────┘
                                                               │
                                                          git push
                                                               │
┌──────────────┐  auth/manage  ┌──────────────┐               │
│   GitHub     │ ◄──────────── │ GitHub CLI   │               │
│ Remote Repo  │               │    (gh)      │               │
└──────┬───────┘               └──────────────┘               │
       └──────────────────────────────────────────────────────┘
```

### Execution Workflow

```
┌───────────┐  runs   ┌────────────────┐  opens   ┌───────────┐ selects ┌────────┐
│ Python 3  │ ──────► │ run_catalog.py │ ───────► │  tkinter  │ ──────► │ Photo  │
│Interpreter│          │  Entry Point   │           │Folder Pick│         │ Folder │
└───────────┘          └───────┬────────┘           └───────────┘         └────────┘
                               │ calls
                               ▼
                       ┌────────────────┐
                       │photo_catalog.py│
                       │  Core Logic    │
                       └──┬──────────┬──┘
                  reads   │          │  writes
                          ▼          ▼
                  ┌───────────┐  ┌──────────┐     ┌────────┐
                  │Pillow(PIL)│  │ openpyxl │ ──► │ .xlsx  │
                  │EXIF Reader│  │Excel Write│     │ Output │
                  └───────────┘  └──────────┘     └────────┘
```

**How it works:**
1. Python executes run_catalog.py, which opens a tkinter folder picker dialog
2. Once a folder is selected, photo_catalog.py is called
3. Pillow reads EXIF/XMP metadata from each image file
4. openpyxl writes the formatted Excel spreadsheet with all metadata
5. Face recognition runs as an optional second pass (if enabled)

---

## 6. Common Git Workflow

### Making Changes

| Step | Command | What It Does |
|------|---------|-------------|
| 1 | Edit files in VS Code | Make your code changes and save |
| 2 | `git status` | See which files have been modified |
| 3 | `git add <files>` | Stage the files you want to commit |
| 4 | `git commit -m "message"` | Save a snapshot with a descriptive message |
| 5 | `git push` | Upload your commits to GitHub |

### Viewing History

| Command | Purpose |
|---------|---------|
| `git log --oneline` | View commit history (compact) |
| `git diff` | See unstaged changes |
| `gh repo view --web` | Open the repo on GitHub in your browser |

---

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| ModuleNotFoundError: No module named 'PIL' | Run: `pip install Pillow` |
| ModuleNotFoundError: No module named 'openpyxl' | Run: `pip install openpyxl` |
| FileNotFoundError for output directory | Create the output folder: `mkdir output` |
| gh: command not recognized | Close and reopen VS Code after installing GitHub CLI |
| Folder picker does not appear | Ensure tkinter is included in your Python installation |
