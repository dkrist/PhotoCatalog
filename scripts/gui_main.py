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
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
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
from copy_engine import (
    copy_to_destination,
    delete_non_keepers,
    find_empty_source_folders,
    move_non_keepers,
    remove_empty_source_folders,
)
from duplicate_detector import compute_md5, detect_duplicates_on_workbook  # noqa: F401
from folder_composer import (
    DAY_FORMATS,
    FolderConfig,
    MONTH_FORMATS,
    YEAR_FORMATS,
    make_folder_config_from_settings,
    preview_example,
)
from rename_engine import (
    RENAME_VARIABLES,
    build_renames,
    check_template_viability,
    test_template,
)
from rollback import find_latest_journal, undo_journal
from settings import get_settings


# ---------------------------------------------------------------------------
# Paths and metadata
# ---------------------------------------------------------------------------
APP_TITLE = "The Photo Catalog Project"
APP_VERSION = "V3"
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
        dupe_mode: str = "none",
        folder_config: Optional[FolderConfig] = None,
        destination_folder: Optional[str] = None,
        rename_template: str = "",
        always_hash_all_files: bool = False,
    ) -> None:
        super().__init__()
        self._folder = folder
        self._output_dir = output_dir
        self._enable_faces = enable_faces
        self._output_path = output_path
        self._dupe_mode = dupe_mode
        self._folder_config = folder_config
        self._destination_folder = destination_folder
        self._rename_template = rename_template
        self._always_hash_all_files = always_hash_all_files
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
                dupe_mode=self._dupe_mode,
                folder_config=self._folder_config,
                destination_folder=self._destination_folder,
                rename_template=self._rename_template,
                always_hash_all_files=self._always_hash_all_files,
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
# v3 workers — Copy / Move / Delete / Undo
# ---------------------------------------------------------------------------
# Each of these wraps a single copy_engine or rollback function and
# forwards progress/log over Qt signals. They share the same signal
# shape as CatalogWorker so the main window's signal-handler surface
# stays small: progress(int, int, str), log(str), finished(dict),
# failed(str), cancelled().
class _V3WorkerBase(QObject):
    """Common signals + cancel plumbing for the v3 destination workers."""
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()


class CopyWorker(_V3WorkerBase):
    """Runs :func:`copy_engine.copy_to_destination` off the UI thread."""

    def __init__(self, xlsx_path: str, destination_folder: str) -> None:
        super().__init__()
        self._xlsx_path = xlsx_path
        self._destination_folder = destination_folder

    def run(self) -> None:
        try:
            summary = copy_to_destination(
                xlsx_path=self._xlsx_path,
                destination_folder=self._destination_folder,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
            )
            if summary.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(summary)
        except Exception as e:  # noqa: BLE001
            logging.exception("Copy worker failed")
            self.failed.emit(str(e))


class MoveNonKeepersWorker(_V3WorkerBase):
    """Runs :func:`copy_engine.move_non_keepers` off the UI thread."""

    def __init__(self, xlsx_path: str, holding_folder: str) -> None:
        super().__init__()
        self._xlsx_path = xlsx_path
        self._holding_folder = holding_folder

    def run(self) -> None:
        try:
            summary = move_non_keepers(
                xlsx_path=self._xlsx_path,
                holding_folder=self._holding_folder,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
            )
            if summary.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(summary)
        except Exception as e:  # noqa: BLE001
            logging.exception("Move-non-keepers worker failed")
            self.failed.emit(str(e))


class DeleteNonKeepersWorker(_V3WorkerBase):
    """Runs :func:`copy_engine.delete_non_keepers` off the UI thread."""

    def __init__(self, xlsx_path: str, rollback_dir: str) -> None:
        super().__init__()
        self._xlsx_path = xlsx_path
        self._rollback_dir = rollback_dir

    def run(self) -> None:
        try:
            summary = delete_non_keepers(
                xlsx_path=self._xlsx_path,
                rollback_dir=self._rollback_dir,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
            )
            if summary.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(summary)
        except Exception as e:  # noqa: BLE001
            logging.exception("Delete-non-keepers worker failed")
            self.failed.emit(str(e))


class UndoWorker(_V3WorkerBase):
    """Runs :func:`rollback.undo_journal` off the UI thread."""

    def __init__(self, journal_path: str, dest_folder: str) -> None:
        super().__init__()
        self._journal_path = journal_path
        self._dest_folder = dest_folder

    def run(self) -> None:
        try:
            counters = undo_journal(
                journal_path=self._journal_path,
                dest_folder=self._dest_folder,
                log_callback=lambda msg: self.log.emit(msg),
            )
            self.finished.emit(counters)
        except Exception as e:  # noqa: BLE001
            logging.exception("Undo worker failed")
            self.failed.emit(str(e))


class DetectDupesWorker(_V3WorkerBase):
    """
    Runs :func:`duplicate_detector.detect_duplicates_on_workbook` off the
    UI thread so the GUI stays responsive while hashing a large drive.

    Used by the "Detect Duplicates on Existing Workbook" button, which
    exists so the user can add dupe info to a workbook that was produced
    with ``dupe_mode="none"`` without having to re-scan the whole folder.
    """

    def __init__(
        self,
        xlsx_path: str,
        mode: str,
        always_hash_all_files: bool = False,
    ) -> None:
        super().__init__()
        self._xlsx_path = xlsx_path
        self._mode = mode
        self._always_hash_all_files = always_hash_all_files

    def run(self) -> None:
        try:
            summary = detect_duplicates_on_workbook(
                xlsx_path=self._xlsx_path,
                mode=self._mode,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=lambda msg: self.log.emit(msg),
                cancel_event=self._cancel,
                always_hash_all_files=self._always_hash_all_files,
            )
            if summary.get("cancelled"):
                self.cancelled.emit()
            else:
                self.finished.emit(summary)
        except Exception as e:  # noqa: BLE001
            logging.exception("Detect-dupes worker failed")
            self.failed.emit(str(e))


class _ProgressFormatProxy:
    """
    Tiny shim that lets call-sites keep using
    ``self.progress_counter.setText("Copying\u2026")`` after the counter
    QLabel was retired and folded into the progress bar's text display.

    The proxy holds a reference to the QProgressBar and routes
    ``setText(s)`` to ``bar.setFormat(s)``, so the status text now
    renders inside the bar itself instead of in a separate label to
    its right. Saves a row of vertical space without forcing every
    progress update site in the file to be rewritten.
    """

    def __init__(self, bar: QProgressBar) -> None:
        self._bar = bar

    def setText(self, text: str) -> None:  # noqa: N802 - QLabel API parity
        self._bar.setFormat(text)

    def text(self) -> str:
        return self._bar.format()


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
        # v3 destination-side workers share the same (worker, thread)
        # slot because only one of them can run at a time anyway.
        self.v3_worker: Optional[_V3WorkerBase] = None
        self.v3_thread: Optional[QThread] = None
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
        # The Duplicate Detection combo used to live here as its own
        # row, but feedback was that it sat too far away from the
        # "Detect Duplicates" button that uses it. It now lives on the
        # v3 action row directly to the left of that button. Start
        # Cataloging still reads the same control regardless of where
        # it's placed in the layout.
        root.addLayout(self._build_action_buttons_row())
        # The standalone progress section + its 20px cushion that used
        # to live here moved to the bottom of the window: the progress
        # bar now sits on the same row as the "Process Log Messages"
        # header so live-run feedback is co-located with the log scroll.
        root.addLayout(self._build_report_buttons_row())
        root.addWidget(self._build_rename_section())
        # Destination Folder + Folder Layout block sits immediately
        # before the Copy/Move/Delete/Undo row so the destination-side
        # controls read top-down as "where" → "how (layout)" → "do".
        root.addLayout(self._build_folder_row(
            "Destination Folder (for Copy pass)",
            "destination_folder_edit",
            self._on_browse_destination_folder,
        ))
        root.addWidget(self._build_folder_layout_section())
        root.addLayout(self._build_v3_action_buttons_row())
        root.addLayout(self._build_log_header_row())
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

    def _build_progress_bar(self) -> QProgressBar:
        """
        Construct the single progress bar widget used by every
        long-running operation. Status text (e.g. "Copying\u2026",
        "1,234 / 1,305", "Detection done") renders *inside* the bar via
        its format string; we no longer need a separate counter QLabel
        next to it. ``self.progress_counter`` is kept as a proxy so
        existing call-sites (`progress_counter.setText(...)`) continue
        to work without rewrites.

        The bar lives on the same row as the "Process Log Messages"
        header and gets ``stretch=1`` there so it takes the full
        remaining width \u2014 important for the indeterminate marquee
        animation used by Undo and Pre-Scan to read smoothly.
        """
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Ready")
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #e6e6e6; border: 1px solid #bfbfbf; "
            "color: #1f3a66; font-weight: bold; }"
            "QProgressBar::chunk { background-color: #6dbf57; }"
        )
        # Adapter: lets every existing self.progress_counter.setText(...)
        # call-site keep working unchanged \u2014 the text now lands
        # inside the bar via setFormat.
        self.progress_counter = _ProgressFormatProxy(self.progress_bar)
        return self.progress_bar

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

    # ---- v3 UI sections --------------------------------------------------

    def _build_folder_layout_section(self) -> QWidget:
        """
        Destination folder-layout picker (three enable checkboxes + a
        format radio group for each). Levels always render Year \u2192
        Month \u2192 Day in that order so the UI only exposes the
        format choices, not the ordering.

        A live example label at the bottom renders June 15, 2019 under
        whatever combination the user has currently selected so they
        know exactly what to expect before committing to a run.
        """
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        label = QLabel("Destination Folder Layout")
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        outer.addWidget(label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        # --- Year row -----------------------------------------------------
        self.year_checkbox = QCheckBox("Year folder")
        self.year_checkbox.toggled.connect(self._on_folder_layout_changed)
        grid.addWidget(self.year_checkbox, 0, 0)
        self.year_format_group = QButtonGroup(self)
        self.year_format_radios: dict = {}
        for col, fmt in enumerate(YEAR_FORMATS, start=1):
            rb = QRadioButton(fmt)
            rb.toggled.connect(self._on_folder_layout_changed)
            self.year_format_group.addButton(rb)
            self.year_format_radios[fmt] = rb
            grid.addWidget(rb, 0, col)

        # --- Month row ----------------------------------------------------
        self.month_checkbox = QCheckBox("Month folder")
        self.month_checkbox.toggled.connect(self._on_folder_layout_changed)
        grid.addWidget(self.month_checkbox, 1, 0)
        self.month_format_group = QButtonGroup(self)
        self.month_format_radios: dict = {}
        for col, fmt in enumerate(MONTH_FORMATS, start=1):
            rb = QRadioButton(fmt)
            rb.toggled.connect(self._on_folder_layout_changed)
            self.month_format_group.addButton(rb)
            self.month_format_radios[fmt] = rb
            grid.addWidget(rb, 1, col)

        # --- Day row ------------------------------------------------------
        self.day_checkbox = QCheckBox("Day folder")
        self.day_checkbox.toggled.connect(self._on_folder_layout_changed)
        grid.addWidget(self.day_checkbox, 2, 0)
        self.day_format_group = QButtonGroup(self)
        self.day_format_radios: dict = {}
        for col, fmt in enumerate(DAY_FORMATS, start=1):
            rb = QRadioButton(fmt)
            rb.toggled.connect(self._on_folder_layout_changed)
            self.day_format_group.addButton(rb)
            self.day_format_radios[fmt] = rb
            grid.addWidget(rb, 2, col)

        outer.addLayout(grid)

        # Live preview label — updated every time the user flips a
        # checkbox/radio. Seeded with a default so the label isn't blank
        # before any interaction.
        self.folder_layout_preview = QLabel("Example: 2019\\06 - June")
        self.folder_layout_preview.setStyleSheet("color: #555555; font-style: italic;")
        outer.addWidget(self.folder_layout_preview)

        return wrap

    # NOTE: _build_dupe_mode_row was removed in 3.0.1 — the Duplicate
    # Detection combo it used to build is now created inline by
    # _build_v3_action_buttons_row so it sits directly to the left of
    # the "Detect Duplicates" button that consumes its value.

    def _build_v3_action_buttons_row(self) -> QHBoxLayout:
        """
        Row of destination-side action buttons: [Duplicate Detection
        combo] [Detect Duplicates] [Copy to Destination] [Move non-keepers]
        [Delete non-keepers] [Undo Last Operation].

        The Duplicate Detection combo lives on this row (rather than up
        with the cataloging controls) because it's the input the
        "Detect Duplicates" button reads at click time \u2014 keeping
        them adjacent makes the dependency obvious. Start Cataloging
        also reads this same combo, just from a different code path.

        All action buttons are disabled until a workbook exists on disk.
        Move and Delete additionally require a dupe-detection pass to
        have populated File_DupeKeep \u2014 that's enforced at click time
        so the user sees a helpful message if they try to use them
        without having detected duplicates.
        """
        row = QHBoxLayout()
        row.setSpacing(8)

        # --- Duplicate Detection combo (input for the button to its right)
        dupe_label = QLabel("Duplicate Detection:")
        dupe_label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        row.addWidget(dupe_label)

        self.dupe_mode_combo = QComboBox()
        # (display, setting_value) pairs. Keep the setting_value in sync
        # with _VALID_DUPE_MODES in settings.py.
        for display, value in (
            ("None", "none"),
            ("Filename + Size (fast)", "filename_size"),
            ("MD5 Hash (thorough, slower)", "hash"),
        ):
            self.dupe_mode_combo.addItem(display, value)
        self.dupe_mode_combo.currentIndexChanged.connect(self._on_dupe_mode_changed)
        row.addWidget(self.dupe_mode_combo)

        # "Hash all files" opt-out for the smart-hash optimization.
        # Default OFF (= optimization ON), because skipping size-unique
        # files saves 80–95% of MD5 I/O on a typical photo library
        # without affecting correctness. Tick this only when you want
        # the File_Hash column populated for every row (e.g. as a
        # standalone checksum independent of duplicate detection).
        # Greyed out unless MD5 Hash mode is currently selected, since
        # the flag has no effect for None / Filename+Size modes.
        self.always_hash_checkbox = QCheckBox("Hash all files")
        self.always_hash_checkbox.setToolTip(
            "When unchecked (default), MD5 mode skips files whose size "
            "is unique across the library — they cannot have a "
            "byte-identical twin so hashing them is wasted I/O. "
            "Tick this to force a full MD5 sweep over every file (much "
            "slower; only useful if you want File_Hash populated for "
            "every row regardless of duplicate detection)."
        )
        self.always_hash_checkbox.toggled.connect(self._on_always_hash_toggled)
        row.addWidget(self.always_hash_checkbox)

        # "Detect Duplicates on Existing Workbook" — lets the user add
        # File_Hash / File_DupeGroup / File_DupeKeep columns to a workbook
        # produced with dupe_mode="none" without re-scanning the source
        # tree. Uses whatever mode is currently selected in the combo
        # immediately to the left (None is rejected at click time).
        self.detect_dupes_button = QPushButton("Detect Duplicates")
        self.detect_dupes_button.setFixedWidth(170)
        self.detect_dupes_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.detect_dupes_button.setEnabled(False)
        self.detect_dupes_button.setToolTip(
            "Run duplicate detection against the current workbook using "
            "the mode selected in the Duplicate Detection combo to the "
            "left. Useful when the catalog was produced with Duplicate "
            "Detection = None."
        )
        self.detect_dupes_button.clicked.connect(self._on_detect_dupes_on_workbook)
        row.addWidget(self.detect_dupes_button)

        self.copy_button = QPushButton("Copy to Destination")
        self.copy_button.setFixedWidth(170)
        self.copy_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._on_copy_to_destination)
        row.addWidget(self.copy_button)

        self.move_dupe_button = QPushButton("Move non-keepers")
        self.move_dupe_button.setFixedWidth(170)
        self.move_dupe_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.move_dupe_button.setEnabled(False)
        self.move_dupe_button.clicked.connect(self._on_move_non_keepers)
        row.addWidget(self.move_dupe_button)

        self.delete_dupe_button = QPushButton("Delete non-keepers")
        self.delete_dupe_button.setFixedWidth(170)
        self.delete_dupe_button.setStyleSheet(
            "QPushButton { background-color: #a73a3a; color: white; font-weight: bold;"
            " border: 1px solid #6f2626; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #c14747; }"
            "QPushButton:pressed { background-color: #7f2c2c; }"
            "QPushButton:disabled { background-color: #c6a0a0; color: #f0f0f0;"
            " border: 1px solid #9d7575; }"
        )
        self.delete_dupe_button.setEnabled(False)
        self.delete_dupe_button.clicked.connect(self._on_delete_non_keepers)
        row.addWidget(self.delete_dupe_button)

        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.setFixedWidth(180)
        self.undo_button.setStyleSheet(BLUE_BUTTON_STYLE)
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self._on_undo_last)
        row.addWidget(self.undo_button)

        row.addStretch(1)
        return row

    def _build_log_header_row(self) -> QHBoxLayout:
        """
        Combined header row that sits directly above the log panel:
        the "Process Log Messages" section label on the left and the
        run-status progress bar taking the remaining width to the right.

        Pairing them on a single row means status feedback is co-located
        with the log scroll \u2014 the user only has to look in one
        place during a run \u2014 and reclaims the vertical space the
        old standalone progress section used to consume.
        """
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel("Process Log Messages")
        label.setStyleSheet("color: #2f5b9a; font-weight: bold;")
        row.addWidget(label)

        # stretch=1 so the bar takes the rest of the row \u2014 important
        # for the indeterminate marquee animation to read smoothly.
        row.addWidget(self._build_progress_bar(), 1)
        return row

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
        self.destination_folder_edit.setText(
            self.settings.get("destination_folder", "")
        )

        # Rename template — round-trip through settings so the last
        # template the user used is restored on next launch.
        self.rename_template_edit.setText(self.settings.get("rename_template", ""))

        # Folder-layout checkboxes + format radios (v3). Defaults are
        # already in settings, so this unconditionally restores saved state.
        self.year_checkbox.setChecked(bool(self.settings.get("folder_level_year")))
        self.month_checkbox.setChecked(bool(self.settings.get("folder_level_month")))
        self.day_checkbox.setChecked(bool(self.settings.get("folder_level_day")))
        year_fmt = self.settings.get("folder_format_year") or "YYYY"
        month_fmt = self.settings.get("folder_format_month") or "MM - MonthName"
        day_fmt = self.settings.get("folder_format_day") or "DD"
        if year_fmt in self.year_format_radios:
            self.year_format_radios[year_fmt].setChecked(True)
        if month_fmt in self.month_format_radios:
            self.month_format_radios[month_fmt].setChecked(True)
        if day_fmt in self.day_format_radios:
            self.day_format_radios[day_fmt].setChecked(True)

        # Dupe-mode combo: find the setting_value we stored in item data.
        saved_dupe = self.settings.get("dupe_mode") or "none"
        for i in range(self.dupe_mode_combo.count()):
            if self.dupe_mode_combo.itemData(i) == saved_dupe:
                self.dupe_mode_combo.setCurrentIndex(i)
                break

        # Smart-hash opt-out checkbox — restore last-used value.
        self.always_hash_checkbox.setChecked(
            bool(self.settings.get("always_hash_all_files"))
        )

        # Any edit to either folder invalidates the pre-scan gating so the
        # user has to re-scan before they can start cataloging.
        self.photo_folder_edit.textChanged.connect(self._on_folder_input_changed)
        self.report_folder_edit.textChanged.connect(self._on_folder_input_changed)
        self.destination_folder_edit.textChanged.connect(
            self._on_destination_folder_changed
        )

        # Refresh the layout preview now that radios/checkboxes reflect
        # the saved state.
        self._refresh_folder_layout_preview()
        self._update_button_states()

    # ---- Button enable/disable logic ------------------------------------

    def _on_folder_input_changed(self, _text: str) -> None:
        """Invalidate pre-scan state and refresh button enablement."""
        # Changing the photo folder invalidates any prior pre-scan result.
        current_photo = self.photo_folder_edit.text().strip()
        if self.prescanned_folder is not None and current_photo != self.prescanned_folder:
            self.prescanned_folder = None
        self._update_button_states()

    # ---- v3 small handlers ----------------------------------------------

    def _on_destination_folder_changed(self, _text: str) -> None:
        """Destination is only used by the v3 action buttons; just refresh."""
        self._update_button_states()

    def _on_folder_layout_changed(self, _checked: bool = False) -> None:
        """Any checkbox or radio flip just re-renders the preview."""
        self._refresh_folder_layout_preview()

    def _on_dupe_mode_changed(self, _index: int) -> None:
        """Saved on Start; no side effects to apply immediately."""
        # We intentionally don't persist here — settings are saved when
        # the user actually kicks off a catalog run so half-edited
        # combos don't leak back into the config file mid-session.
        pass

    def _on_always_hash_toggled(self, _checked: bool) -> None:
        """Smart-hash opt-out toggle. Persisted on the next Start/Detect."""
        # Same rationale as _on_dupe_mode_changed: defer persistence to
        # the action handlers so the user can flip it freely without
        # mutating the config file in real time.
        pass

    def _current_folder_config(self) -> FolderConfig:
        """Read the current checkbox/radio state into a FolderConfig."""
        def _picked(group: dict, default: str) -> str:
            for fmt, rb in group.items():
                if rb.isChecked():
                    return fmt
            return default

        return FolderConfig(
            level_year=self.year_checkbox.isChecked(),
            format_year=_picked(self.year_format_radios, "YYYY"),
            level_month=self.month_checkbox.isChecked(),
            format_month=_picked(self.month_format_radios, "MM - MonthName"),
            level_day=self.day_checkbox.isChecked(),
            format_day=_picked(self.day_format_radios, "DD"),
        )

    def _refresh_folder_layout_preview(self) -> None:
        """Update the example label under the Folder Layout grid."""
        try:
            example = preview_example(self._current_folder_config())
        except ValueError as e:
            example = f"(invalid: {e})"
        self.folder_layout_preview.setText(f"Example: {example}")

    def _persist_v3_settings(self) -> None:
        """
        Round-trip every v3 UI selection into the settings singleton.
        Called from the v3 action handlers (Start Cataloging, Copy,
        Move, Delete) so the user's current configuration sticks across
        launches.
        """
        cfg = self._current_folder_config()
        try:
            self.settings.set("destination_folder", self.destination_folder_edit.text())
            self.settings.set("rename_template", self.rename_template_edit.text())
            self.settings.set("folder_level_year", cfg.level_year)
            self.settings.set("folder_format_year", cfg.format_year)
            self.settings.set("folder_level_month", cfg.level_month)
            self.settings.set("folder_format_month", cfg.format_month)
            self.settings.set("folder_level_day", cfg.level_day)
            self.settings.set("folder_format_day", cfg.format_day)
            self.settings.set(
                "dupe_mode",
                self.dupe_mode_combo.currentData() or "none",
            )
            self.settings.set(
                "always_hash_all_files",
                bool(self.always_hash_checkbox.isChecked()),
            )
            self.settings.save()
        except ValueError as e:
            # Surface but don't crash — a bad value should never happen
            # from the UI (every control is constrained to valid inputs)
            # but if it does we'd rather log than abort the run.
            logging.warning("Could not persist v3 settings: %s", e)

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
        destination_folder = self.destination_folder_edit.text().strip() \
            if hasattr(self, "destination_folder_edit") else ""
        running = (
            (self.worker_thread is not None and self.worker_thread.isRunning())
            or (self.prescan_thread is not None and self.prescan_thread.isRunning())
            or (self.rename_thread is not None and self.rename_thread.isRunning())
            or (self.v3_thread is not None and self.v3_thread.isRunning())
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

        # v3 destination-side buttons:
        #   Copy requires a workbook + a destination folder.
        #   Move/Delete additionally require that dupe detection actually
        #     produced File_DupeKeep values — but enforcing that here
        #     would require reading the workbook on every state update,
        #     so we defer that check to click time.
        #   Undo requires a rollback journal to exist in the destination.
        copy_ok = report_exists and bool(destination_folder) and not running
        move_ok = copy_ok  # click-time validation enforces dupe pass
        delete_ok = copy_ok
        undo_ok = copy_ok  # click-time validation verifies journal exists
        # Detect Duplicates only needs a workbook — it rewrites the
        # workbook in place, so the Destination Folder isn't relevant.
        detect_ok = report_exists and not running
        if hasattr(self, "detect_dupes_button"):
            self.detect_dupes_button.setEnabled(detect_ok)
        if hasattr(self, "copy_button"):
            self.copy_button.setEnabled(copy_ok)
        if hasattr(self, "move_dupe_button"):
            self.move_dupe_button.setEnabled(move_ok)
        if hasattr(self, "delete_dupe_button"):
            self.delete_dupe_button.setEnabled(delete_ok)
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(undo_ok)

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

    def _on_browse_destination_folder(self) -> None:
        """v3 destination-root picker (Copy / Move / Delete target)."""
        start = self.destination_folder_edit.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Destination Folder", start,
        )
        if folder:
            self.destination_folder_edit.setText(folder)

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

        # v3 — persist the destination / layout / dupe selections too so
        # everything the catalog run is about to use is pinned in settings.
        self._persist_v3_settings()

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

        # v3 params for the pipeline. destination_folder only matters when
        # folder_config is also supplied (see run_catalog docstring).
        destination_folder = self.destination_folder_edit.text().strip()
        folder_config = self._current_folder_config() if destination_folder else None
        dupe_mode = self.dupe_mode_combo.currentData() or "none"
        rename_template = self.rename_template_edit.text()
        always_hash_all_files = bool(self.always_hash_checkbox.isChecked())

        # Spin up the worker on a dedicated QThread.
        self.worker_thread = QThread(self)
        self.worker = CatalogWorker(
            folder=photo_folder,
            output_dir=report_folder,
            enable_faces=self.settings.get("enable_face_recognition", True),
            output_path=final_output_path,
            dupe_mode=dupe_mode,
            folder_config=folder_config,
            destination_folder=destination_folder or None,
            rename_template=rename_template,
            always_hash_all_files=always_hash_all_files,
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

    # ---- v3 destination-side actions -------------------------------------

    def _spin_v3_worker(
        self,
        worker: "_V3WorkerBase",
        on_finished,
        on_cancelled=None,
    ) -> None:
        """
        Shared QThread spin-up for Copy / Move / Delete / Undo workers.
        Takes care of wiring signals, disabling buttons during the run,
        and cleaning up on completion.
        """
        self.v3_thread = QThread(self)
        self.v3_worker = worker
        worker.moveToThread(self.v3_thread)
        self.v3_thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._append_log)
        worker.finished.connect(on_finished)
        worker.failed.connect(self._on_v3_failed)
        if on_cancelled is not None:
            worker.cancelled.connect(on_cancelled)
        else:
            worker.cancelled.connect(self._on_v3_cancelled)
        for sig in (worker.finished, worker.failed, worker.cancelled):
            sig.connect(self.v3_thread.quit)
        self.v3_thread.finished.connect(self.v3_thread.deleteLater)
        self.v3_thread.finished.connect(self._reset_after_v3)
        self._update_button_states()
        self.v3_thread.start()

    def _on_v3_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Operation failed", message)

    def _on_v3_cancelled(self) -> None:
        self._append_log("Operation cancelled by user.")

    def _reset_after_v3(self) -> None:
        self.v3_worker = None
        self.v3_thread = None
        self._update_button_states()

    def _require_workbook_and_destination(self, action: str) -> Optional[tuple]:
        """
        Shared click-time validation for the v3 action buttons. Returns
        ``(xlsx_path, destination_folder)`` on success, or None if the
        action can't proceed (with a warning dialog already shown).
        """
        if not self.last_report_path or not os.path.exists(self.last_report_path):
            QMessageBox.information(
                self, f"{action} — no report",
                "Run Start Cataloging first so there's a workbook to operate on.",
            )
            return None
        destination = self.destination_folder_edit.text().strip()
        if not destination:
            QMessageBox.warning(
                self, f"{action} — no destination",
                "Please choose a Destination Folder before running this action.",
            )
            return None
        if is_file_locked(self.last_report_path):
            QMessageBox.warning(
                self, f"{action} — report in use",
                "The report workbook is open in another application and can't be "
                "updated. Close it and try again.",
            )
            return None
        return self.last_report_path, destination

    def _on_copy_to_destination(self) -> None:
        """Copy every row to its File_DestPath under the destination root."""
        resolved = self._require_workbook_and_destination("Copy to Destination")
        if resolved is None:
            return
        xlsx_path, destination = resolved
        self._persist_v3_settings()

        reply = QMessageBox.question(
            self,
            "Copy to Destination",
            "This will copy every file in the catalog to the destination "
            "folder using the pre-computed File_DestPath values, write a "
            "rollback journal to the destination for Undo, and update "
            "File_Status in the workbook.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Copying\u2026")
        self._append_log(f"=== Copy to Destination: {destination} ===")
        self._spin_v3_worker(
            CopyWorker(xlsx_path=xlsx_path, destination_folder=destination),
            on_finished=self._on_copy_finished,
        )

    def _on_copy_finished(self, summary: dict) -> None:
        self._append_log(
            f"Copy complete: {summary.get('copied', 0):,} copied, "
            f"{summary.get('sidecars', 0):,} sidecar(s), "
            f"{summary.get('skipped', 0):,} skipped, "
            f"{summary.get('errors', 0):,} error(s)."
        )
        empties = summary.get("empty_source_folders") or []
        if empties:
            self._append_log(
                f"{len(empties):,} empty source folder(s) detected — "
                "remove with 'Delete non-keepers' follow-up if desired."
            )
        self.progress_counter.setText("Copy done")

    def _on_move_non_keepers(self) -> None:
        """Move File_DupeKeep=FALSE rows into a holding subfolder."""
        resolved = self._require_workbook_and_destination("Move non-keepers")
        if resolved is None:
            return
        xlsx_path, destination = resolved
        self._persist_v3_settings()

        # Holding folder lives inside the destination root by convention
        # so the rollback journal ends up beside the moved files.
        holding_folder = os.path.join(destination, "_DupeHolding")

        reply = QMessageBox.question(
            self,
            "Move non-keepers",
            "This will MOVE every row flagged File_DupeKeep=FALSE in the "
            "workbook into the following holding folder:\n\n"
            f"{holding_folder}\n\n"
            "A rollback journal will be written so the move can be undone.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Moving\u2026")
        self._append_log(f"=== Move non-keepers to: {holding_folder} ===")
        self._spin_v3_worker(
            MoveNonKeepersWorker(
                xlsx_path=xlsx_path, holding_folder=holding_folder,
            ),
            on_finished=self._on_move_finished,
        )

    def _on_move_finished(self, summary: dict) -> None:
        self._append_log(
            f"Move complete: {summary.get('moved', 0):,} moved, "
            f"{summary.get('skipped', 0):,} skipped, "
            f"{summary.get('errors', 0):,} error(s)."
        )
        self.progress_counter.setText("Move done")

    def _on_delete_non_keepers(self) -> None:
        """Delete File_DupeKeep=FALSE rows in place (destructive)."""
        resolved = self._require_workbook_and_destination("Delete non-keepers")
        if resolved is None:
            return
        xlsx_path, destination = resolved
        self._persist_v3_settings()

        # Belt-and-braces: require a typed confirmation so an accidental
        # click can't wipe hundreds of files.
        reply = QMessageBox.warning(
            self,
            "Delete non-keepers — DESTRUCTIVE",
            "This will PERMANENTLY DELETE every file flagged "
            "File_DupeKeep=FALSE in the workbook. A rollback journal will "
            "record what was deleted, but the file bytes are NOT recoverable "
            "from the journal alone.\n\n"
            "It is strongly recommended to run 'Move non-keepers' first "
            "and verify the holding folder before running Delete.\n\n"
            "Are you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Deleting\u2026")
        self._append_log("=== Delete non-keepers (rollback journal in destination) ===")
        self._spin_v3_worker(
            DeleteNonKeepersWorker(
                xlsx_path=xlsx_path, rollback_dir=destination,
            ),
            on_finished=self._on_delete_finished,
        )

    def _on_delete_finished(self, summary: dict) -> None:
        self._append_log(
            f"Delete complete: {summary.get('deleted', 0):,} deleted, "
            f"{summary.get('skipped', 0):,} skipped, "
            f"{summary.get('errors', 0):,} error(s)."
        )
        self.progress_counter.setText("Delete done")

    def _on_undo_last(self) -> None:
        """Reverse the most recent rollback journal in the destination."""
        destination = self.destination_folder_edit.text().strip()
        if not destination or not os.path.isdir(destination):
            QMessageBox.warning(
                self, "Undo — no destination",
                "Please pick the Destination Folder that holds the "
                "rollback journal you want to undo.",
            )
            return
        journal = find_latest_journal(destination)
        if journal is None:
            QMessageBox.information(
                self, "Undo — nothing to undo",
                "No rollback journal was found in the destination folder.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Undo Last Operation",
            f"Reverse the operations recorded in:\n\n{journal}\n\n"
            "Copies will be removed, moves will be moved back, deletes will "
            "be reported as unrecoverable (bytes are gone). A matching "
            "_undo_*.jsonl journal will be written for audit.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_counter.setText("Undoing\u2026")
        self._append_log(f"=== Undo: {journal} ===")
        self._spin_v3_worker(
            UndoWorker(journal_path=str(journal), dest_folder=destination),
            on_finished=self._on_undo_finished,
        )

    def _on_undo_finished(self, counters: dict) -> None:
        self._append_log(
            f"Undo complete: {counters.get('undone', 0):,} reversed, "
            f"{counters.get('skipped', 0):,} skipped, "
            f"{counters.get('failed', 0):,} failed, "
            f"{counters.get('unrecoverable', 0):,} unrecoverable."
        )
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_counter.setText("Undo done")

    def _on_detect_dupes_on_workbook(self) -> None:
        """
        Run duplicate detection against ``self.last_report_path`` using
        the mode currently selected in the Duplicate Detection combo.

        Intended for recovering from a catalog run where the user left
        the combo on "None" — the workbook already exists, we just need
        to hash (if requested), group, and write the dupe columns back.
        """
        if not self.last_report_path or not os.path.exists(self.last_report_path):
            QMessageBox.information(
                self, "Detect Duplicates — no report",
                "Run Start Cataloging first so there's a workbook to operate on.",
            )
            return
        if is_file_locked(self.last_report_path):
            QMessageBox.warning(
                self, "Detect Duplicates — report in use",
                "The report workbook is open in another application and can't "
                "be updated. Close it and try again.",
            )
            return

        mode = self.dupe_mode_combo.currentData() or "none"
        if mode == "none":
            QMessageBox.information(
                self, "Detect Duplicates — select a mode",
                "Please pick either 'Filename + Size (fast)' or "
                "'MD5 Hash (thorough, slower)' in the Duplicate Detection "
                "combo above, then click this button again.",
            )
            return

        # Confirm — hash mode can be slow and both modes rewrite the file.
        mode_label = "Filename + Size" if mode == "filename_size" else "MD5 Hash"
        extra_note = (
            "\n\nNOTE: MD5 Hash mode re-reads every file on disk whose "
            "path in the workbook still resolves, so this can take a "
            "while on a large library."
            if mode == "hash" else ""
        )
        reply = QMessageBox.question(
            self,
            "Detect Duplicates on Existing Workbook",
            f"Run duplicate detection ({mode_label}) against:\n\n"
            f"{self.last_report_path}\n\n"
            "This will write File_Hash / File_DupeGroup / File_DupeKeep "
            "values back into the workbook and highlight grouped rows "
            "in orange on the File_Name column."
            f"{extra_note}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._persist_v3_settings()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_counter.setText("Detecting duplicates\u2026")
        self._append_log(
            f"=== Detect Duplicates on Workbook ({mode_label}) ==="
        )
        self._spin_v3_worker(
            DetectDupesWorker(
                xlsx_path=self.last_report_path,
                mode=mode,
                always_hash_all_files=bool(self.always_hash_checkbox.isChecked()),
            ),
            on_finished=self._on_detect_dupes_finished,
        )

    def _on_detect_dupes_finished(self, summary: dict) -> None:
        self._append_log(
            f"Detection complete: {summary.get('groups', 0):,} group(s), "
            f"{summary.get('duplicate_rows', 0):,} row(s) in groups, "
            f"{summary.get('keepers', 0):,} keeper(s), "
            f"{summary.get('non_keepers', 0):,} non-keeper(s), "
            f"{summary.get('skipped', 0):,} skipped."
        )
        missing = summary.get("missing_on_disk", 0)
        if missing:
            self._append_log(
                f"  {missing:,} row(s) had a File_Path that no longer "
                "exists on disk — those rows had no hash computed."
            )
        self.progress_bar.setValue(100)
        self.progress_counter.setText("Detection done")

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

        # v3 Copy/Move/Delete/Undo worker — same shape as rename cancel.
        if self.v3_thread is not None and self.v3_thread.isRunning():
            if self.v3_worker is not None:
                self.v3_worker.cancel()
            self.v3_thread.quit()
            self.v3_thread.wait(3000)

        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
