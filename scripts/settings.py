"""
settings.py — User-configurable application settings for PhotoCatalog.

This module provides a Settings class that loads, saves, and validates
user-facing configuration stored as JSON in the user's app data directory.

Distinguished from config.py:
  - config.py holds developer-level constants (EXIF lookups, XMP namespaces,
    column ordering) that change with code releases.
  - settings.py holds user-level preferences (folder locations, defaults,
    log level) that users may change at runtime.

Typical usage:
    from settings import get_settings

    settings = get_settings()
    report_dir = settings.get("save_report_to")
    settings.set("save_report_to", r"D:\\MyReports")
    settings.save()

Config file location:
    Windows: %APPDATA%\\PhotoCatalog\\config.json
    Other:   ~/.config/PhotoCatalog/config.json
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
# Any setting missing from the user's config.json falls back to these values.
# Paths containing ~ or environment variables like %APPDATA% are expanded
# at load time (see _expand_path).
DEFAULT_SETTINGS: Dict[str, Any] = {
    # Where generated Excel reports are written.
    "save_report_to": str(Path.home() / "Documents" / "PhotoCatalog" / "Reports"),

    # Where application log files are written.
    "log_file_folder": str(Path.home() / "Documents" / "PhotoCatalog" / "Logs"),

    # Default folder presented by the GUI folder picker (empty = last used).
    "default_scan_folder": "",

    # Whether face recognition runs by default (overridden by --no-faces).
    "enable_face_recognition": True,

    # Logging verbosity — one of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    "log_level": "INFO",

    # Recently scanned folders, most recent first (capped at 10).
    "recent_folders": [],
}

# Allowed values for enumerated settings (used by validation).
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_MAX_RECENT_FOLDERS = 10


def _get_config_dir() -> Path:
    """Return the platform-appropriate config directory for PhotoCatalog."""
    # Prefer platformdirs if available (cleaner cross-platform support).
    try:
        from platformdirs import user_config_dir
        return Path(user_config_dir("PhotoCatalog", appauthor=False))
    except ImportError:
        pass

    # Windows fallback: %APPDATA%\PhotoCatalog
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "PhotoCatalog"

    # POSIX fallback: ~/.config/PhotoCatalog
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "PhotoCatalog"
    return Path.home() / ".config" / "PhotoCatalog"


def _expand_path(value: str) -> str:
    """Expand ~ and environment variables (e.g. %APPDATA%) in a path string."""
    if not isinstance(value, str):
        return value
    return os.path.expandvars(os.path.expanduser(value))


class Settings:
    """
    Loads and saves user settings for PhotoCatalog.

    Settings are persisted as JSON. Missing keys fall back to DEFAULT_SETTINGS,
    so new settings added in future versions automatically work with older
    config files.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path: Path = config_path or (_get_config_dir() / "config.json")
        self._values: Dict[str, Any] = {}
        self.load()

    # ---- Loading / saving -------------------------------------------------

    def load(self) -> None:
        """Load settings from disk. Corrupted/missing files regenerate defaults."""
        self._values = dict(DEFAULT_SETTINGS)  # start from defaults
        if not self.config_path.exists():
            # First run — create the file so users can find/edit it.
            self.save()
            return

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("Config root must be a JSON object")
            # Merge user values on top of defaults so unknown future keys survive.
            for key, value in loaded.items():
                if key in DEFAULT_SETTINGS:
                    self._values[key] = value
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logging.warning(
                "Could not read %s (%s). Using defaults and regenerating file.",
                self.config_path, e,
            )
            self.save()

    def save(self) -> None:
        """Write current settings to disk, creating the folder if needed."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._values, f, indent=2, sort_keys=True)
        tmp_path.replace(self.config_path)

    # ---- Accessors --------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return the value for `key`, expanding paths for folder settings.
        Falls back to DEFAULT_SETTINGS, then to `default`.
        """
        if key in ("save_report_to", "log_file_folder", "default_scan_folder"):
            raw = self._values.get(key, DEFAULT_SETTINGS.get(key, default))
            return _expand_path(raw) if raw else raw
        return self._values.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """Validate and set a setting. Call save() to persist."""
        self._validate(key, value)
        self._values[key] = value

    def all(self) -> Dict[str, Any]:
        """Return a copy of all current settings."""
        return dict(self._values)

    # ---- Convenience helpers ---------------------------------------------

    def ensure_folder(self, key: str) -> Path:
        """
        Return the Path for a folder setting, creating it on disk if missing.
        Useful for save_report_to and log_file_folder.
        """
        path = Path(self.get(key))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def add_recent_folder(self, folder: str) -> None:
        """Push `folder` to the front of recent_folders (dedup + cap)."""
        folder = str(folder)
        recents = [f for f in self._values.get("recent_folders", []) if f != folder]
        recents.insert(0, folder)
        self._values["recent_folders"] = recents[:_MAX_RECENT_FOLDERS]

    # ---- Validation -------------------------------------------------------

    @staticmethod
    def _validate(key: str, value: Any) -> None:
        """Raise ValueError if `value` is not valid for `key`."""
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting: {key!r}")

        if key in ("save_report_to", "log_file_folder", "default_scan_folder"):
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string path")

        elif key == "enable_face_recognition":
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a bool")

        elif key == "log_level":
            if not isinstance(value, str) or value.upper() not in _VALID_LOG_LEVELS:
                raise ValueError(
                    f"{key} must be one of {sorted(_VALID_LOG_LEVELS)}"
                )

        elif key == "recent_folders":
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ValueError(f"{key} must be a list of strings")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# Most callers just want "the settings" — this helper returns a shared instance.
_settings_singleton: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the process-wide Settings instance, loading on first access."""
    global _settings_singleton
    if _settings_singleton is None:
        _settings_singleton = Settings()
    return _settings_singleton


if __name__ == "__main__":
    # Running this module directly prints current settings and their location.
    s = get_settings()
    print(f"Config file: {s.config_path}")
    print(json.dumps(s.all(), indent=2))
