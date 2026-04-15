"""
folder_composer.py — Destination folder path composition for PhotoCatalog v3.

Rather than exposing a free-form "folder template" string to the user
(which would require its own viability checker, its own escape rules,
and its own error-prone literal-text parsing) v3 drives the destination
hierarchy with a set of three checkbox/radio pairs:

    [x] Year folder   ( ) YY     (•) YYYY
    [x] Month folder  ( ) MM     (•) MM - MonthName  ( ) MonthName
    [ ] Day folder    ( ) DD     ( ) YYYY-MM-DD

Levels always compose in the order Year → Month → Day; unchecked levels
collapse out of the path. If all three are unchecked, files land flat in
the destination root. Characters illegal on Windows never appear in the
rendered segments because the tokens only produce digits, month names,
and hyphens — but the composer defensively scrubs anyway so one
corrupt configuration can't produce a path Windows would reject.

Public entry points:
    :class:`FolderConfig`  — the checkbox-state bundle passed around.
    :func:`compose_folder` — given a config + a ``datetime``, return the
                             rendered relative folder path (or
                             ``Unknown_Date`` if no date is available).
    :func:`make_folder_config_from_settings` — build a FolderConfig
                             from a :class:`settings.Settings` object.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Allowed format strings
# ---------------------------------------------------------------------------
# Mirrored from settings._VALID_*_FORMATS so the composer can be used
# standalone without importing the full settings module.
YEAR_FORMATS  = ("YY", "YYYY")
MONTH_FORMATS = ("MM", "MM - MonthName", "MonthName")
DAY_FORMATS   = ("DD", "YYYY-MM-DD")

# Literal folder name used when a row has no usable date at all.
UNKNOWN_DATE_FOLDER = "Unknown_Date"

# Windows-illegal filename characters. We only ever need to scrub them
# from month names in practice, but the defensive scrub applies to
# every rendered segment so a future format never accidentally slips
# illegal characters into a destination path.
_ILLEGAL_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FolderConfig:
    """
    Bundle of the six UI controls (three level checkboxes + three
    format pickers) that together describe the destination folder
    layout for a v3 run.

    The GUI builds one on Start Cataloging / Copy and passes it
    through the pipeline so catalog_pipeline and copy_engine don't
    need to know anything about PyQt widgets.
    """
    level_year:   bool = True
    format_year:  str  = "YYYY"
    level_month:  bool = True
    format_month: str  = "MM - MonthName"
    level_day:    bool = False
    format_day:   str  = "DD"

    def validate(self) -> None:
        """
        Raise ValueError if any format string is outside the allowed set.
        The UI should never produce an invalid config; this is a
        belt-and-braces check for callers that construct one by hand.
        """
        if self.format_year not in YEAR_FORMATS:
            raise ValueError(
                f"format_year must be one of {YEAR_FORMATS!r}, got {self.format_year!r}"
            )
        if self.format_month not in MONTH_FORMATS:
            raise ValueError(
                f"format_month must be one of {MONTH_FORMATS!r}, got {self.format_month!r}"
            )
        if self.format_day not in DAY_FORMATS:
            raise ValueError(
                f"format_day must be one of {DAY_FORMATS!r}, got {self.format_day!r}"
            )

    def is_flat(self) -> bool:
        """True if no levels are checked — files will land in dest root."""
        return not (self.level_year or self.level_month or self.level_day)


# ---------------------------------------------------------------------------
# Token rendering helpers
# ---------------------------------------------------------------------------
def _render_year(dt: datetime, fmt: str) -> str:
    return dt.strftime("%y") if fmt == "YY" else dt.strftime("%Y")


def _render_month(dt: datetime, fmt: str) -> str:
    month_num  = dt.strftime("%m")
    month_name = calendar.month_name[dt.month]  # e.g. "June"
    if fmt == "MM":
        return month_num
    if fmt == "MonthName":
        return month_name
    # "MM - MonthName"
    return f"{month_num} - {month_name}"


def _render_day(dt: datetime, fmt: str) -> str:
    if fmt == "YYYY-MM-DD":
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%d")


def _scrub(segment: str) -> str:
    """Remove Windows-illegal characters from one path segment."""
    return _ILLEGAL_WIN_CHARS.sub("", segment).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compose_folder(config: FolderConfig, dt: Optional[datetime]) -> str:
    """
    Compose the relative destination folder path for one row.

    * If *dt* is ``None`` the row has no usable date — return
      :data:`UNKNOWN_DATE_FOLDER` so such rows pile up in one obvious
      place rather than landing flat in the destination root alongside
      correctly-dated files. The caller should also append an
      ``[WARN]`` entry in ``File_Concern`` noting the missing date.
    * If the config is flat (no levels checked) return ``""`` — files
      land flat in the destination root.
    * Otherwise assemble the enabled segments in Year → Month → Day
      order joined with the native path separator.

    The return value is a *relative* path; the caller is responsible
    for joining it to the destination root.
    """
    config.validate()

    if dt is None:
        return UNKNOWN_DATE_FOLDER

    if config.is_flat():
        return ""

    segments = []
    if config.level_year:
        segments.append(_scrub(_render_year(dt, config.format_year)))
    if config.level_month:
        segments.append(_scrub(_render_month(dt, config.format_month)))
    if config.level_day:
        segments.append(_scrub(_render_day(dt, config.format_day)))

    # os.path.join is picky about empty segments on some platforms;
    # filtering now sidesteps "\\2019\\\\" shenanigans on Windows.
    segments = [s for s in segments if s]
    if not segments:
        # All enabled levels scrubbed to empty (shouldn't happen with
        # real dates, but defensive). Fall back to the Unknown bucket
        # so the file still has a destination folder name.
        return UNKNOWN_DATE_FOLDER

    # Use a platform-neutral join that Windows clients will interpret
    # as backslash-separated when joined to a Windows root.
    return "/".join(segments).replace("/", "\\")


def preview_example(config: FolderConfig) -> str:
    """
    Return a human-readable example of what *config* would produce for
    an arbitrary date (June 15, 2019 — same sample the design notes
    use). Handy for the Destination preview label under the checkboxes.
    """
    sample = datetime(2019, 6, 15, 10, 30, 0)
    rendered = compose_folder(config, sample)
    if not rendered:
        return "(flat — files go directly into destination root)"
    return rendered


def make_folder_config_from_settings(settings) -> FolderConfig:
    """
    Build a :class:`FolderConfig` from a loaded :class:`settings.Settings`
    object. Any missing or invalid keys fall back to the settings'
    built-in defaults. Kept thin so the GUI can call it in one line.
    """
    return FolderConfig(
        level_year=bool(settings.get("folder_level_year")),
        format_year=str(settings.get("folder_format_year") or "YYYY"),
        level_month=bool(settings.get("folder_level_month")),
        format_month=str(settings.get("folder_format_month") or "MM - MonthName"),
        level_day=bool(settings.get("folder_level_day")),
        format_day=str(settings.get("folder_format_day") or "DD"),
    )
