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
        self.last_report_path: Optional[str] = None
        self.current_log_file: Optional[str] = None

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
        root.addWidget(self._build_start_button())
        root.addWidget(self._build_progress_section())
        root.addSpacing(20)  # extra breathing room below the progress bar
        root.addLayout(self._build_report_buttons_row())
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

    def _build_start_button(self) -> QPushButton:
        btn = QPushButton("Start Cataloging Process")
        btn.setStyleSheet(
            "QPushButton { background-color: #4f8a3d; color: white; font-weight: bold;"
            " padding: 6px 14px; border: 1px solid #2f5d23; }"
            "QPushButton:disabled { background-color: #9ec589; }"
        )
        btn.setFixedHeight(30)
        btn.setFixedWidth(220)
        btn.clicked.connect(self._on_start_cataloging)
        self.start_button = btn
        return btn

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

    def _on_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Cataloging failed", message)

    def _on_cancelled(self) -> None:
        self._append_log("Cancelled by user.")

    def _reset_after_run(self) -> None:
        self.start_button.setEnabled(True)
        self.worker = None
        self.worker_thread = None

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
        # If a run is in flight, ask the user before closing.
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
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
