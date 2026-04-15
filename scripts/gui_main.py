"""
gui_main.py — PyQt6 desktop UI for PhotoCatalog.

Layout mirrors the wireframe in /Images/PhotoCatalog UI Wireframe.png:

   ┌───────────────────────────────────────────────────────────┐
   │ [cam]  The Photo Catalog Project   v2-4/12/26  Built with │
   │                                                   Claude  │
   ├───────────────────────────────────────────────────────────┤
   │ Select Photo Folder                                       │
   │ [______________________________________]  [Browse]        │
   │                                                           │
   │ Save Report to Folder                                     │
   │ [______________________________________]  [Browse]        │
   │                                                           │
   │ [Start Cataloging Process]                                │
   │                                                           │
   │ Progress                                                  │
   │ [█████████████░░░░░░░░]   nnn,nnn/nnn,nnn                 │
   │                                                           │
   │ [Open Catalog Report]                   [Open Process Log]│
   │ Process Log Messages                                      │
   │ ┌─────────────────────────────────────────────────────┐   │
   │ │                                                     │   │
   │ └─────────────────────────────────────────────────────┘   │
   └───────────────────────────────────────────────────────────┘

Runs the cataloging pipeline on a background QThread so the UI stays
responsive, and streams progress + log messages back via Qt signals.
"""
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Make sibling modules importable whether we run as a script or module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_pipeline import (
    CatalogCancelled,
    default_output_path,
    find_available_path,
    is_file_locked,
    run_catalog,
    run_prescan,
)
from rename_engine import (
    RENAME_VARIABLES,
    build_renames,
    check_template_viability,
    test_template,
)
from settings import get_settings


# ---------------------------------------------------------------------------
# Paths and metadata
# ---------------------------------------------------------------------------
APP_TITLE = "The Photo Catalog Project"
APP_VERSION = "V2"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resource_root() -> Path:
    """Return the folder that contains the bundled ``Images/`` directory.

    In development mode this is the project root (``gui_main.py``'s
    grandparent). When frozen by PyInstaller ``sys._MEIPASS`` points at
    the ``_internal`` directory where data files from the ``.spec`` file
    are unpacked, so the same ``Images/`` subpath resolves correctly in
    both cases.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return PROJECT_ROOT


IMAGES_DIR = _resource_root() / "Images"
CAMERA_ICON = IMAGES_DIR / "camera-icon-52.png"
CLAUDE_ICON = IMAGES_DIR / "250px-Claude_AI_symbol.svg.png"


# Shared button style — blue banner fill with white text.
# Used by Browse, Open Catalog Report, and Open Process Log.
BLUE_BUTTON_STYLE = (
    "QPushButton { background-color: #2f5b9a; color: #ffffff; font-weight: bold;"
    " border: 1px solid #1e3f6f; padding: 4px 10px; }"
    "QPushButton:hover { background-color: #3a6cb0; }"
    "QPushButton:pressed { background-color: #234673; }"
    "QPushButton:disabled { background-color: #8ea6c6; color: #f0f0f0;"
    " border: 1px solid #6f85a3; }"
)


def _build_version_label() -> str:
    """Return 'Vx – M/D/YYYY' using the last-modified date of this source file.

    This means the header date updates automatically whenever the UI code
    is edited — no manual bump required. If the mtime can't be read for
    any reason, today's date is used as a fallback.
    """
    try:
        mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime)
    except OSError:
        mtime = datetime.now()
    return f"{APP_VERSION} \u2013 {mtime.month}/{mtime.day}/{mtime.year}"


# ---------------------------------------------------------------------------
# Worker — runs the pipeline on a background thread
# ---------------------------------------------------------------------------
class CatalogWorker(QObject):
    """
    QObject worker that calls catalog_pipeline.run_catalog and reports
    progress/log/error/finished via Qt signals so the main thread can
    update widgets safely.
    """
    progress = pyqtSignal(int, int, str)   # current, total, filename
    log = pyqtSignal(str)                  # a line of status text
    finished = pyqtSignal(str, int, int)   # output_path, num_rows, num_cols
    failed = pyqtSignal(str)               # error message
    cancelled = pyqtSignal()

    def __init__(
        self,
        folder: str,
        output_dir: str,
        enable_faces: bool,
        output_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._folder = folder
        self._output_dir = output_dir
        self._enable_faces = enable_faces
        self._output_path = output_path
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            out_path, rows, cols = run_catalog(
                folder=self._folder,
                output_dir=self._output_dir,
                enable_faces=self._enable_faces,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
                output_path=self._output_path,
            )
            self.finished.emit(out_path, rows, cols)
        except CatalogCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 - surface any pipeline error to the UI
            logging.exception("Catalog worker failed")
            self.failed.emit(str(e))


class PrescanWorker(QObject):
    """
    QObject worker that calls catalog_pipeline.run_prescan on a background
    thread and reports progress/log/finished via Qt signals.

    The pre-scan only touches filesystem metadata (no image decoding), so
    it's fast — but the total count isn't known until the walk finishes,
    which is why the UI uses an indeterminate progress bar plus a running
    "files seen / folders seen" counter until the scan completes.
    """
    progress = pyqtSignal(int, int)        # files_seen, folders_seen
    log = pyqtSignal(str)                  # a line of status text
    finished = pyqtSignal(dict)            # the full result dict
    failed = pyqtSignal(str)               # error message
    cancelled = pyqtSignal()

    def __init__(self, folder: str) -> None:
        super().__init__()
        self._folder = folder
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = run_prescan(
                folder=self._folder,
                progress_callback=lambda files, folders: self.progress.emit(files, folders),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
            )
            if result.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(result)
        except Exception as e:  # noqa: BLE001 - surface any error to the UI
            logging.exception("Pre-scan worker failed")
            self.failed.emit(str(e))


class RenameWorker(QObject):
    """
    QObject worker that runs rename_engine.build_renames on a background
    thread so the UI stays responsive while the workbook is rewritten.
    """
    progress = pyqtSignal(int, int)    # rows_processed, total_rows
    log = pyqtSignal(str)              # a line of status text
    finished = pyqtSignal(dict)        # summary dict from build_renames
    failed = pyqtSignal(str)           # error message
    cancelled = pyqtSignal()

    def __init__(self, xlsx_path: str, template: str) -> None:
        super().__init__()
        self._xlsx_path = xlsx_path
        self._template = template
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            summary = build_renames(
                xlsx_path=self._xlsx_path,
                template=self._template,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
            )
            if summary.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(summary)
        except Exception as e:  # noqa: BLE001 - surface any error to the UI
            logging.exception("Rename worker failed")
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Top-level window matching the wireframe."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.worker: Optional[CatalogWorker] = None
        self.worker_thread: Optional[QThread] = None
        self.prescan_worker: Optional[PrescanWorker] = None
        self.prescan_thread: Optional[QThread] = None
        self.rename_worker: Optional[RenameWorker] = None
        self.rename_thread: Optional[QThread] = None
        self.last_report_path: Optional[str] = None
        self.current_log_file: Optional[str] = None
        # Pre-scan gating: photo folder must be pre-scanned (and the
        # same folder still selected) before Start Cataloging is enabled.
        self.prescanned_folder: Optional[str] = None

        self._configure_logging()
        self._build_ui()
        self._load_initial_values()

    # ---- Logging setup ---------------------------------------------------

    def _configure_logging(self) -> None:
        """Route logs to a timestamped file in the user's log folder."""
        log_dir = Path(self.settings.ensure_folder("log_file_folder"))
        self.current_log_file = str(
            log_dir / f"photocatalog_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.log"
        )
        level = getattr(logging, self.settings.get("log_level", "INFO").upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.FileHandler(self.current_log_file, encoding="utf-8")],
        )

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(APP_TITLE)
        if CAMERA_ICON.exists():
            self.setWindowIcon(QIcon(str(CAMERA_ICON)))
        self.resize(880, 640)

        central = QWidget(self)
        central.setStyleSheet("background-color: #ffffff;")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())
        root.addLayout(self._build_folder_row(
            "Select Photo Folder", "photo_folder_edit", self._on_browse_photo_folder,
        ))
        root.addLayout(self._build_folder_row(
            "Save Report to Folder", "report_folder_edit", self._on_browse_report_folder,
        ))
        root.addLayout(self._build_action_buttons_row())
        root.addWidget(self._build_progress_section())
        root.addSpacing(20)  # extra breathing room below the progress bar
        root.addLayout(self._build_report_buttons_row())
        root.addWidget(self._build_rename_section())
        root.addWidget(self._build_log_label())
        root.addWidget(self._build_log_panel(), 1)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #2f5b9a; border: 1px solid #1e3f6f; }"
        )
        header.setFixedHeight(70)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)

        # Camera icon
        icon_label = QLabel()
        icon_label.setFixedSize(52, 52)
        if CAMERA_ICON.exists():
            icon_label.setPixmap(
                QPixmap(str(CAMERA_ICON)).scaled(
                    52, 52,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(icon_label)

        # Title
        title = QLabel(APP_TITLE)
        title.setStyleSheet("color: #ffffff; font-size: 22pt; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch(1)

        # Version label — date auto-updates from gui_main.py's mtime
        version = QLabel(_build_version_label())
        version.setStyleSheet("color: #ffffff; font-size: 10pt; font-weight: bold;")
        layout.addWidget(version)
        layout.addSpacing(20)

        # "Built with Claude" chip — no border, transparent so it sits flush
        # on the blue header.
        built_frame = QFrame()
        built_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        built_layout = QHBoxLayout(built_frame)
        built_layout.setContentsMargins(0, 0, 0, 0)
        built_label = QLabel("Built with\nClaude")
        built_label.setStyleSheet(
            "color: #ffffff; background: transparent; font-size: 9pt; font-weight: bold;"
        )
        built_layout.addWidget(built_label)

        # Size the Claude mark closer to the 52px camera icon on the left
        # so the two header marks read as visually balanced.
        claude_icon = QLabel()
        claude_icon.setFixedSize(44, 44)
        claude_icon.setStyleSheet("background: transparent; border: none;")
        if CLAUDE_ICON.exists():
            claude_icon.setPixmap(
                QPixmap(str(CLAUDE_ICON)).scaled(
                    44, 44,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        built_layout.addWidget(claude_icon)
        layout.addWidget(built_frame)

        return header

    def _build_folder_row(self, label_text: str, attr_name: str, on_browse) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        box.addWidget(label)

        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setReadOnly(False)  # user may paste / type a path
        edit.setMinimumHeight(26)
        setattr(self, attr_name, edit)
        row.addWidget(edit, 1)

        browse = QPushButton("Browse")
        browse.setFixedWidth(90)
        browse.setStyleSheet(BLUE_BUTTON_STYLE)
        browse.clicked.connect(on_browse)
        row.addWidget(browse)
        box.addLayout(row)
        return box

    def _build_action_buttons_row(self) -> QHBoxLayout:
        """Row of action buttons: [Pre-Scan Folder] [Start Cataloging Process]."""
        row = QHBoxLayout()
        row.setSpacing(10)

        # Pre-Scan — blue so it visually matches the other utility buttons
        # (Browse, Open Report, Open Log). Disabled until the report folder
        # has been chosen.
        prescan = QPushButton("Pre-Scan Folder")
        prescan.setStyleSheet(BLUE_BUTTON_STYLE)
        prescan.setFixedHeight(30)
        prescan.setFixedWidth(180)
        prescan.setEnabled(False)
        prescan.clicked.connect(self._on_prescan)
        self.prescan_button = prescan
        row.addWidget(prescan)

        # Start Cataloging — green, disabled until pre-scan completes.
        start = QPushButton("Start Cataloging Process")
        start.setStyleSheet(
            "QPushButton { background-color: #4f8a3d; color: white; font-weight: bold;"
            " padding: 6px 14px; border: 1px solid #2f5d23; }"
            "QPushButton:disabled { background-color: #9ec589; }"
        )
        start.setFixedHeight(30)
        start.setFixedWidth(220)
        start.setEnabled(False)
        start.clicked.connect(self._on_start_cataloging)
        self.start_button = start
        row.addWidget(start)

        row.addStretch(1)
        return row

    def _build_progress_section(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("Progress")
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        layout.addWidget(label)

        row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #e6e6e6; border: 1px solid #bfbfbf; }"
            "QProgressBar::chunk { background-color: #6dbf57; }"
        )
        row.addWidget(self.progress_bar, 1)

        # Idle text shown before the first run; replaced with "current/total"
        # by _on_progress as soon as the worker emits its first update.
        self.progress_counter = QLabel("Ready")
        self.progress_counter.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        self.progress_counter.setMinimumWidth(140)
        self.progress_counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.progress_counter)

        layout.addLayout(row)
        return wrap

    def _build_report_buttons_row(self) -> QHBoxLayout:
        """Build the row with [Open Catalog Report] [Open Process Log]."""
        row = QHBoxLayout()

        self.open_report_button = QPushButton("Open Catalog Report")
        self.open_report_button.setFixedWidth(180)
        self.open_report_button.setEnabled(False)
        self.open_report_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.open_report_button.clicked.connect(self._on_open_report)
        row.addWidget(self.open_report_button)

        self.open_log_button = QPushButton("Open Process Log")
        self.open_log_button.setFixedWidth(160)
        self.open_log_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.open_log_button.clicked.connect(self._on_open_log)
        row.addWidget(self.open_log_button)

        row.addStretch(1)
        return row

    def _build_rename_section(self) -> QWidget:
        """
        Rename File Name Template section — sits between the Open
        Report/Log row and the Process Log panel.

        Contents:
          * Section label + a one-line help blurb listing valid
            %Variable% tokens
          * Single-line text box for the template string
          * Row of two buttons: Test Rename String + Build Renames
            for all Photos (both disabled until a catalog report is
            available and the user has typed something in the box)
        """
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("Rename File Name Template")
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        layout.addWidget(label)

        # Show valid variables inline so the user doesn't need a
        # separate cheat sheet. Tokens are small, plain grey.
        help_text = "Variables: " + "  ".join(RENAME_VARIABLES.keys())
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: #555555; font-size: 9pt;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.rename_template_edit = QLineEdit()
        self.rename_template_edit.setPlaceholderText(
            "e.g.  %Date_YYYY%-%Date_MM%-%Date_DD%_%Camera_Make%_%File_Name%%File_Extension%"
        )
        self.rename_template_edit.setMinimumHeight(26)
        self.rename_template_edit.textChanged.connect(self._on_rename_template_changed)
        layout.addWidget(self.rename_template_edit)

        button_row = QHBoxLayout()
        self.test_rename_button = QPushButton("Test Rename String")
        self.test_rename_button.setFixedWidth(180)
        self.test_rename_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.test_rename_button.setEnabled(False)
        self.test_rename_button.clicked.connect(self._on_test_rename)
        button_row.addWidget(self.test_rename_button)

        self.build_rename_button = QPushButton("Build Renames for all Photos")
        self.build_rename_button.setFixedWidth(230)
        self.build_rename_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.build_rename_button.setEnabled(False)
        self.build_rename_button.clicked.connect(self._on_build_renames)
        button_row.addWidget(self.build_rename_button)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        return wrap

    def _build_log_label(self) -> QLabel:
        """Section label above the log panel."""
        label = QLabel("Process Log Messages")
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        return label

    def _build_log_panel(self) -> QTextEdit:
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QTextEdit { background-color: #ffffff; border: 1px solid #bfbfbf; }"
        )
        self.log_view.setMinimumHeight(160)
        return self.log_view

    # ---- Initial values from settings ------------------------------------

    def _load_initial_values(self) -> None:
        self.photo_folder_edit.setText(self.settings.get("default_scan_folder", ""))
        self.report_folder_edit.setText(self.settings.get("save_report_to", ""))

        # Any edit to either folder invalidates the pre-scan gating so the
        # user has to re-scan before they can start cataloging.
        self.photo_folder_edit.textChanged.connect(self._on_folder_input_changed)
        self.report_folder_edit.textChanged.connect(self._on_folder_input_changed)
        self._update_button_states()

    # ---- Button enable/disable logic ------------------------------------

    def _on_folder_input_changed(self, _text: str) -> None:
        """Invalidate pre-scan state and refresh button enablement."""
        # Changing the photo folder invalidates any prior pre-scan result.
        current_photo = self.photo_folder_edit.text().strip()
        if self.prescanned_folder is not None and current_photo != self.prescanned_folder:
            self.prescanned_folder = None
        self._update_button_states()

    def _update_button_states(self) -> None:
        """
        Rules (from the v2.1 Change Request):
          * Pre-Scan is enabled when both folders are populated and valid,
            and no worker is currently running.
          * Start Cataloging is enabled only after a successful pre-scan
            of the currently-selected photo folder.
          * Test Rename String / Build Renames are enabled once a
            catalog workbook exists on disk and the user has typed a
            non-empty template. Disabled while any worker is running.
        """
        photo_folder = self.photo_folder_edit.text().strip()
        report_folder = self.report_folder_edit.text().strip()
        running = (
            (self.worker_thread is not None and self.worker_thread.isRunning())
            or (self.prescan_thread is not None and self.prescan_thread.isRunning())
            or (self.rename_thread is not None and self.rename_thread.isRunning())
        )

        photo_ok = bool(photo_folder) and os.path.isdir(photo_folder)
        report_ok = bool(report_folder)

        self.prescan_button.setEnabled(photo_ok and report_ok and not running)
        self.start_button.setEnabled(
            photo_ok
            and report_ok
            and self.prescanned_folder == photo_folder
            and not running
        )

        # Rename buttons: require a workbook on disk + a non-empty
        # template. We only check for existence — validation of the
        # template tokens happens at click time so the user sees a
        # helpful message instead of a silently greyed-out button.
        report_exists = bool(
            self.last_report_path and os.path.exists(self.last_report_path)
        )
        template_present = bool(
            getattr(self, "rename_template_edit", None)
            and self.rename_template_edit.text().strip()
        )
        rename_ok = report_exists and template_present and not running
        if hasattr(self, "test_rename_button"):
            self.test_rename_button.setEnabled(rename_ok)
        if hasattr(self, "build_rename_button"):
            self.build_rename_button.setEnabled(rename_ok)

    # ---- Browse handlers -------------------------------------------------

    def _on_browse_photo_folder(self) -> None:
        start = self.photo_folder_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Photo Folder", start)
        if folder:
            self.photo_folder_edit.setText(folder)

    def _on_browse_report_folder(self) -> None:
        start = self.report_folder_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Save Report Folder", start)
        if folder:
            self.report_folder_edit.setText(folder)

    # ---- Pre-scan / worker plumbing -------------------------------------

    def _on_prescan(self) -> None:
        photo_folder = self.photo_folder_edit.text().strip()
        report_folder = self.report_folder_edit.text().strip()

        if not photo_folder or not os.path.isdir(photo_folder):
            QMessageBox.warning(self, "Invalid photo folder",
                                "Please select a valid photo folder to pre-scan.")
            return
        if not report_folder:
            QMessageBox.warning(self, "Invalid report folder",
                                "Please select where the report should be saved.")
            return

        # Persist the user's choices right away so pre-scanning a folder
        # also remembers it for the next launch.
        try:
            self.settings.set("default_scan_folder", photo_folder)
            self.settings.set("save_report_to", report_folder)
            self.settings.save()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid setting", str(e))
            return

        # Prep the UI: clear log, switch the progress bar to indeterminate
        # (marquee) mode since we don't know the total count until the walk
        # finishes, and disable both action buttons during the scan.
        self.log_view.clear()
        self.progress_bar.setRange(0, 0)   # indeterminate / marquee mode
        self.progress_counter.setText("Scanning…")
        self.prescan_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.prescanned_folder = None

        # Spin up the worker on a dedicated QThread.
        self.prescan_thread = QThread(self)
        self.prescan_worker = PrescanWorker(folder=photo_folder)
        self.prescan_worker.moveToThread(self.prescan_thread)
        self.prescan_thread.started.connect(self.prescan_worker.run)
        self.prescan_worker.progress.connect(self._on_prescan_progress)
        self.prescan_worker.log.connect(self._append_log)
        self.prescan_worker.finished.connect(self._on_prescan_finished)
        self.prescan_worker.failed.connect(self._on_prescan_failed)
        self.prescan_worker.cancelled.connect(self._on_prescan_cancelled)
        for sig in (
            self.prescan_worker.finished,
            self.prescan_worker.failed,
            self.prescan_worker.cancelled,
        ):
            sig.connect(self.prescan_thread.quit)
        self.prescan_thread.finished.connect(self.prescan_thread.deleteLater)
        self.prescan_thread.finished.connect(self._reset_after_prescan)
        self.prescan_thread.start()

    def _on_prescan_progress(self, files_seen: int, folders_seen: int) -> None:
        # Keep the indeterminate bar spinning and just refresh the counter.
        self.progress_counter.setText(
            f"Scanning… {files_seen:,} files in {folders_seen:,} folders"
        )

    def _on_prescan_finished(self, result: dict) -> None:
        # Pre-scan is the gate for cataloging, so remember which folder
        # was scanned — if the user edits the photo folder later we'll
        # require a fresh scan before Start becomes available again.
        self.prescanned_folder = self.photo_folder_edit.text().strip()

        total_files = result.get("total_files", 0)
        total_folders = result.get("total_folders", 0)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_counter.setText(
            f"{total_files:,} files / {total_folders:,} folders"
        )

    def _on_prescan_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Ready")
        QMessageBox.critical(self, "Pre-scan failed", message)

    def _on_prescan_cancelled(self) -> None:
        self._append_log("Pre-scan cancelled by user.")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Ready")

    def _reset_after_prescan(self) -> None:
        self.prescan_worker = None
        self.prescan_thread = None
        self._update_button_states()

    # ---- Start / worker plumbing ----------------------------------------

    def _on_start_cataloging(self) -> None:
        photo_folder = self.photo_folder_edit.text().strip()
        report_folder = self.report_folder_edit.text().strip()

        if not photo_folder or not os.path.isdir(photo_folder):
            QMessageBox.warning(self, "Invalid photo folder",
                                "Please select a valid photo folder to catalog.")
            return
        if not report_folder:
            QMessageBox.warning(self, "Invalid report folder",
                                "Please select where the report should be saved.")
            return

        # Persist the user's choices immediately.
        try:
            self.settings.set("default_scan_folder", photo_folder)
            self.settings.set("save_report_to", report_folder)
            self.settings.add_recent_folder(photo_folder)
            self.settings.save()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid setting", str(e))
            return

        # Pre-flight: make sure the target Excel file isn't currently open.
        # This saves the user from waiting through a long run only to hit a
        # PermissionError at the end. Returns None if the user cancels.
        os.makedirs(report_folder, exist_ok=True)
        final_output_path = self._resolve_output_path(photo_folder, report_folder)
        if final_output_path is None:
            return  # user cancelled

        # Reset progress UI and disable Start to prevent double-runs.
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Scanning…")
        self.start_button.setEnabled(False)
        self.open_report_button.setEnabled(False)
        self._append_log(f"Starting catalog of: {photo_folder}")
        self._append_log(f"Report will be saved to: {final_output_path}")

        # Spin up the worker on a dedicated QThread.
        self.worker_thread = QThread(self)
        self.worker = CatalogWorker(
            folder=photo_folder,
            output_dir=report_folder,
            enable_faces=self.settings.get("enable_face_recognition", True),
            output_path=final_output_path,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        # Ensure the thread quits once any terminal signal fires.
        for sig in (self.worker.finished, self.worker.failed, self.worker.cancelled):
            sig.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._reset_after_run)
        self.worker_thread.start()

    # ---- Pre-flight output-path resolution -------------------------------

    def _resolve_output_path(self, photo_folder: str, report_folder: str) -> Optional[str]:
        """
        Determine the Excel path to write to, handling file-lock conflicts.

        Flow:
          1. Compute the default date-based filename.
          2. If it doesn't exist or isn't locked, return it.
          3. If it's locked (e.g. open in Excel), show a dialog letting the
             user Retry after closing the file, Save as a New Version (auto
             _2, _3, ... suffix), or Cancel.

        Returns the chosen path, or None if the user cancels.
        """
        target = default_output_path(photo_folder, report_folder)

        while is_file_locked(target):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Report file is in use")
            box.setText(
                "The target report file is currently open in another "
                "application and can't be overwritten:"
            )
            box.setInformativeText(target)
            retry_btn = box.addButton("Retry", QMessageBox.ButtonRole.AcceptRole)
            newver_btn = box.addButton(
                "Save as New Version", QMessageBox.ButtonRole.ActionRole,
            )
            cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(retry_btn)
            box.exec()

            clicked = box.clickedButton()
            if clicked is retry_btn:
                # Loop checks the lock again on the next iteration.
                continue
            if clicked is newver_btn:
                versioned = find_available_path(target)
                self._append_log(
                    f"Original report is locked; saving as new version: "
                    f"{os.path.basename(versioned)}"
                )
                return versioned
            # Cancel button (or dialog closed)
            return None

        return target

    # ---- Signal handlers -------------------------------------------------

    def _on_progress(self, current: int, total: int, _filename: str) -> None:
        if total <= 0:
            return
        pct = int(current * 100 / total)
        self.progress_bar.setValue(pct)
        # Match the wireframe format: nnn,nnn/nnn,nnn
        self.progress_counter.setText(f"{current:,}/{total:,}")

    def _append_log(self, message: str) -> None:
        logging.info(message)
        self.log_view.append(message)
        # Auto-scroll to bottom.
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _on_finished(self, output_path: str, num_rows: int, num_cols: int) -> None:
        self.last_report_path = output_path
        self.open_report_button.setEnabled(True)
        self._append_log(f"Finished: {num_rows} photos x {num_cols} columns")
        self._append_log(f"Report: {output_path}")
        # A fresh workbook is now on disk, so the Rename buttons can
        # light up (assuming the user has typed a template).
        self._update_button_states()

    def _on_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Cataloging failed", message)

    def _on_cancelled(self) -> None:
        self._append_log("Cancelled by user.")

    def _reset_after_run(self) -> None:
        self.worker = None
        self.worker_thread = None
        self._update_button_states()

    # ---- Rename template plumbing ---------------------------------------

    def _on_rename_template_changed(self, _text: str) -> None:
        """Refresh rename-button enablement whenever the template edits."""
        self._update_button_states()

    def _template_viability_dialog(self, template: str, action: str) -> bool:
        """
        CR #2 shared preflight for Test Rename String and Build Renames.

        Runs :func:`check_template_viability` on the template and decides
        what dialog (if any) to show:

        * **Errors present** \u2014 blocking critical dialog that lists
          every error *and every warning* in one pass, plus the valid-
          variable cheat sheet. The user fixes everything they see and
          clicks OK; no proceed option. Returns ``False``.
        * **Warnings only** \u2014 Yes/No question dialog listing the
          warnings. Returns ``True`` on Yes, ``False`` on No.
        * **Clean template** \u2014 no dialog, returns ``True``.

        Showing errors and warnings together avoids a two-step "fix
        one thing \u2192 click Test again \u2192 discover the next thing"
        loop that was reported as poor UX.

        *action* is the title-case verb ("Test Rename" / "Build Renames")
        shown in the dialog title so the user knows what they're gating.
        """
        errors, warnings = check_template_viability(template)
        if errors:
            sections = [
                "The rename template cannot be used as-is.",
                "",
                "Errors (must be fixed):",
                "\n".join(f"  \u2022 {e}" for e in errors),
            ]
            if warnings:
                # Surface warnings in the same dialog so the user can
                # address everything in one pass rather than discovering
                # them one at a time on subsequent attempts.
                sections.extend([
                    "",
                    "Warnings (would need your confirmation after errors are fixed):",
                    "\n".join(f"  \u2022 {w}" for w in warnings),
                ])
            sections.extend([
                "",
                "Valid variables:",
                "\n".join(f"  {k}" for k in RENAME_VARIABLES.keys()),
            ])
            QMessageBox.critical(
                self, f"{action} \u2014 invalid template", "\n".join(sections),
            )
            log_line = f"Template rejected: {'; '.join(errors)}"
            if warnings:
                log_line += f" | warnings pending: {'; '.join(warnings)}"
            self._append_log(log_line)
            return False
        if warnings:
            msg = (
                "The rename template has the following potential issues:\n\n  \u2022 "
                + "\n  \u2022 ".join(warnings)
                + "\n\nProceed anyway?"
            )
            reply = QMessageBox.question(
                self, f"{action} \u2014 template warning", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._append_log(
                    f"Template warnings acknowledged \u2014 user cancelled {action}."
                )
                return False
            for w in warnings:
                self._append_log(f"Warning acknowledged: {w}")
        return True

    def _on_test_rename(self) -> None:
        """
        Validate the template and preview the first 10 rendered names
        from the last-saved workbook in the Process Log.
        """
        template = self.rename_template_edit.text()
        if not self.last_report_path or not os.path.exists(self.last_report_path):
            QMessageBox.information(
                self, "No report yet",
                "Run the cataloging process first so there's a workbook to read from.",
            )
            return

        self._append_log(f"=== Test Rename \u2014 Template: {template} ===")
        # CR #2: gate on viability before doing any rendering.
        if not self._template_viability_dialog(template, "Test Rename"):
            return

        try:
            result = test_template(
                xlsx_path=self.last_report_path,
                template=template,
                row_limit=10,
            )
        except Exception as e:  # noqa: BLE001
            logging.exception("Test rename failed")
            self._append_log(f"ERROR: {e}")
            QMessageBox.critical(self, "Test Rename failed", str(e))
            return

        previews = result.get("previews", [])
        total = result.get("total_rows", 0)
        self._append_log(
            f"Previewing {len(previews)} of {total:,} rows:"
        )
        for i, (original, rendered, reason) in enumerate(previews, start=1):
            if rendered is not None:
                self._append_log(f"  {i:>2}. {original}  \u2192  {rendered}")
            else:
                self._append_log(
                    f"  {i:>2}. {original}  \u2192  (skipped \u2014 {reason})"
                )

    def _on_build_renames(self) -> None:
        """Kick off a background rename pass across every row."""
        template = self.rename_template_edit.text()
        if not self.last_report_path or not os.path.exists(self.last_report_path):
            QMessageBox.information(
                self, "No report yet",
                "Run the cataloging process first so there's a workbook to read from.",
            )
            return

        # CR #2: gate on viability before doing any work so the user
        # isn't waiting on a preflight render to discover the template
        # was broken.
        if not self._template_viability_dialog(template, "Build Renames"):
            return

        # Can't write to the workbook while it's open in Excel.
        if is_file_locked(self.last_report_path):
            QMessageBox.warning(
                self, "Report file is in use",
                "The report workbook is currently open in another application "
                "and can't be updated. Close it and try again.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Build Renames for all Photos",
            "This will write a rendered filename into the File_RenameName "
            "column for every row in the current catalog workbook, "
            "validate for collisions / length / empty renders (flagged "
            "in File_Concern), and save the file.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Reset progress UI for the rename pass.
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Renaming\u2026")
        self._append_log(
            f"=== Build Renames \u2014 Template: {template} ==="
        )

        self.rename_thread = QThread(self)
        self.rename_worker = RenameWorker(
            xlsx_path=self.last_report_path, template=template,
        )
        self.rename_worker.moveToThread(self.rename_thread)
        self.rename_thread.started.connect(self.rename_worker.run)
        self.rename_worker.progress.connect(self._on_rename_progress)
        self.rename_worker.log.connect(self._append_log)
        self.rename_worker.finished.connect(self._on_rename_finished)
        self.rename_worker.failed.connect(self._on_rename_failed)
        self.rename_worker.cancelled.connect(self._on_rename_cancelled)
        for sig in (
            self.rename_worker.finished,
            self.rename_worker.failed,
            self.rename_worker.cancelled,
        ):
            sig.connect(self.rename_thread.quit)
        self.rename_thread.finished.connect(self.rename_thread.deleteLater)
        self.rename_thread.finished.connect(self._reset_after_rename)
        self._update_button_states()
        self.rename_thread.start()

    def _on_rename_progress(self, done: int, total: int) -> None:
        if total <= 0:
            return
        pct = int(done * 100 / total)
        self.progress_bar.setValue(pct)
        self.progress_counter.setText(f"{done:,}/{total:,}")

    def _on_rename_finished(self, summary: dict) -> None:
        total = summary.get("total", 0)
        renamed = summary.get("renamed", 0)
        skipped = summary.get("skipped", []) or []
        fallback_dates = summary.get("fallback_dates", 0)
        errors = summary.get("errors", 0)
        self._append_log(
            f"Rename complete: {renamed:,} of {total:,} rows renamed, "
            f"{len(skipped):,} skipped."
        )
        # CR #1: surface the fallback-date count and validation errors
        # as a one-liner so the user sees the gist without scrolling.
        if fallback_dates or errors:
            self._append_log(
                f"  File_Concern summary: {fallback_dates:,} used File_Date fallback, "
                f"{errors:,} rows flagged [ERROR] "
                f"(collision / length / empty render)."
            )
        if skipped:
            # Summarize skip reasons so the user sees patterns (e.g.
            # "200 rows missing DateTimeOriginal and File_Date")
            # without scrolling through every filename.
            reasons: dict = {}
            for _name, reason in skipped:
                reasons[reason] = reasons.get(reason, 0) + 1
            for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
                self._append_log(f"  {count:>6,} skipped \u2014 {reason}")
        self.progress_counter.setText(f"{renamed:,}/{total:,}")

    def _on_rename_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Build Renames failed", message)

    def _on_rename_cancelled(self) -> None:
        self._append_log("Rename cancelled by user.")

    def _reset_after_rename(self) -> None:
        self.rename_worker = None
        self.rename_thread = None
        self._update_button_states()

    # ---- Open report / log ----------------------------------------------

    def _on_open_report(self) -> None:
        if self.last_report_path and os.path.exists(self.last_report_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_report_path))
        else:
            QMessageBox.information(self, "No report yet",
                                    "Run the cataloging process first.")

    def _on_open_log(self) -> None:
        if self.current_log_file and os.path.exists(self.current_log_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_log_file))
        else:
            QMessageBox.information(self, "No log file",
                                    "The log file hasn't been created yet.")

    # ---- Window lifecycle -----------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        # If a catalog run is in flight, ask the user before closing.
        if self.worker_thread is not None and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self, "Cataloging in progress",
                "A cataloging run is still in progress. Cancel it and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.worker is not None:
                self.worker.cancel()
            self.worker_thread.quit()
            self.worker_thread.wait(3000)

        # A pre-scan can also be in flight — cancel it silently since it
        # doesn't produce output the user cares about.
        if self.prescan_thread is not None and self.prescan_thread.isRunning():
            if self.prescan_worker is not None:
                self.prescan_worker.cancel()
            self.prescan_thread.quit()
            self.prescan_thread.wait(3000)

        # A rename pass may also be in flight — cancel it so the
        # workbook isn't left half-updated. build_renames only saves
        # when the full walk completes, so a cancel here is safe.
        if self.rename_thread is not None and self.rename_thread.isRunning():
            if self.rename_worker is not None:
                self.rename_worker.cancel()
            self.rename_thread.quit()
            self.rename_thread.wait(3000)

        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
