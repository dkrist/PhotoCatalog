"""
rollback.py — Per-run JSONL journal for v3 destructive-ish operations.

Every Copy / Move-non-keepers / Delete-non-keepers pass writes a
``_rollback_<YYYYMMDD_HHMMSS>.jsonl`` file in the destination folder,
one line per filesystem operation. The Undo Last Operation button
reads the newest journal in reverse and reverses each entry.

Journal line shape:
    {
      "ts": "2026-04-15T09:30:12",
      "op": "copy" | "move" | "delete" | "mkdir" | "rmdir",
      "src": "<absolute source path>",
      "dst": "<absolute destination path>" (absent for delete/rmdir),
      "sidecar_of": "<primary absolute path>" (absent unless this is a sidecar copy)
    }

Public entry points:
    :class:`RollbackWriter` — context-manager helper that creates and
        appends to a journal file.
    :func:`find_latest_journal` — locate the most recent
        ``_rollback_*.jsonl`` in a destination folder.
    :func:`undo_journal`        — read a journal in reverse and reverse
        every operation, writing a matching ``_undo_*.jsonl`` for
        auditability.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


_JOURNAL_PREFIX = "_rollback_"
_UNDO_PREFIX    = "_undo_"
_JOURNAL_EXT    = ".jsonl"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------
class RollbackWriter:
    """
    Append-only JSONL journal writer.

    Usage::

        with RollbackWriter(dest_folder) as rb:
            rb.record("copy", src="A", dst="B")
            rb.record("copy", src="A.xmp", dst="B.xmp", sidecar_of="A")

    The file is created on first record so a pass that raises before
    doing any work leaves no stray journal behind.
    """

    def __init__(self, dest_folder: str, tag: str = "rollback") -> None:
        self._dest = Path(dest_folder)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # tag lets callers stamp a different prefix (e.g. "undo") so
        # the undo operation's own journal is labelled distinctly.
        prefix = _UNDO_PREFIX if tag == "undo" else _JOURNAL_PREFIX
        self._path = self._dest / f"{prefix}{timestamp}{_JOURNAL_EXT}"
        self._file = None
        self._count = 0

    # Allow use as a plain object or a context manager.
    def __enter__(self) -> "RollbackWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def entry_count(self) -> int:
        return self._count

    def record(self, op: str, **fields) -> None:
        """Append one op record. File is created lazily on first call."""
        if self._file is None:
            self._dest.mkdir(parents=True, exist_ok=True)
            # Line-buffered so a crash still leaves valid JSONL up to the
            # last completed line.
            self._file = self._path.open("a", encoding="utf-8", buffering=1)
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "op": op}
        entry.update(fields)
        self._file.write(json.dumps(entry) + "\n")
        self._count += 1

    def close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None


# ---------------------------------------------------------------------------
# Reader helpers
# ---------------------------------------------------------------------------
def find_latest_journal(dest_folder: str) -> Optional[Path]:
    """
    Return the most-recent ``_rollback_*.jsonl`` file in *dest_folder*
    based on filename timestamp (which equals mtime order in practice).
    Undo journals are intentionally excluded — we undo the most recent
    real operation, not a previous undo.
    """
    dest = Path(dest_folder)
    if not dest.is_dir():
        return None
    candidates = sorted(
        (p for p in dest.glob(f"{_JOURNAL_PREFIX}*{_JOURNAL_EXT}") if p.is_file()),
        key=lambda p: p.name,
    )
    return candidates[-1] if candidates else None


def load_journal(path: str) -> List[Dict]:
    """Load all entries from *path* in order. Invalid lines are skipped."""
    entries: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logging.warning("Rollback journal %s line %d malformed", path, lineno)
    return entries


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------
def _undo_copy(entry: Dict) -> str:
    """
    Delete the destination file that was created by a prior copy.
    Returns a short human-readable status string.
    """
    dst = entry.get("dst")
    if not dst:
        return "skipped — no dst in entry"
    if not os.path.exists(dst):
        return f"skipped — already gone: {dst}"
    try:
        os.remove(dst)
        return f"removed {dst}"
    except OSError as e:
        return f"FAILED to remove {dst}: {e}"


def _undo_move(entry: Dict) -> str:
    """Move the file back from dst → src."""
    src = entry.get("src")
    dst = entry.get("dst")
    if not src or not dst:
        return "skipped — move entry missing src/dst"
    if not os.path.exists(dst):
        return f"skipped — dst gone: {dst}"
    try:
        os.makedirs(os.path.dirname(src), exist_ok=True)
        shutil.move(dst, src)
        return f"moved {dst} → {src}"
    except OSError as e:
        return f"FAILED to move {dst} → {src}: {e}"


def _undo_delete(entry: Dict) -> str:
    """
    Deletes can only be undone if the original file still exists
    somewhere (e.g. Recycle Bin, backup). For the journaled case we
    don't have bytes on hand, so we report the missing source for
    the user to recover manually.
    """
    src = entry.get("src")
    return f"CANNOT auto-undo delete: {src} (restore from backup if needed)"


def _undo_mkdir(entry: Dict) -> str:
    """Remove a directory that was created during the run, if empty."""
    dst = entry.get("dst")
    if not dst:
        return "skipped — no dst"
    if not os.path.isdir(dst):
        return f"skipped — dir gone: {dst}"
    try:
        os.rmdir(dst)
        return f"removed empty dir {dst}"
    except OSError:
        return f"skipped — dir not empty: {dst}"


def _undo_rmdir(entry: Dict) -> str:
    """Recreate a directory that was removed during source cleanup."""
    src = entry.get("src")
    if not src:
        return "skipped — no src"
    try:
        os.makedirs(src, exist_ok=True)
        return f"recreated {src}"
    except OSError as e:
        return f"FAILED to recreate {src}: {e}"


_UNDO_DISPATCH: Dict[str, Callable[[Dict], str]] = {
    "copy":   _undo_copy,
    "move":   _undo_move,
    "delete": _undo_delete,
    "mkdir":  _undo_mkdir,
    "rmdir":  _undo_rmdir,
}


def undo_journal(
    journal_path: str,
    dest_folder: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict:
    """
    Reverse every entry in *journal_path* in reverse order, writing a
    matching ``_undo_*.jsonl`` for auditability.

    Returns a summary dict with counts for 'undone', 'skipped',
    'failed', and 'unrecoverable' (deletes whose source is gone).
    """
    log = log_callback or (lambda _m: None)
    entries = load_journal(journal_path)
    log(f"Undo: loaded {len(entries)} entries from {journal_path}")

    counters = {"undone": 0, "skipped": 0, "failed": 0, "unrecoverable": 0}

    with RollbackWriter(dest_folder, tag="undo") as undo_rb:
        # Reverse order so nested mkdir/copy pairs unwind cleanly.
        for entry in reversed(entries):
            op = entry.get("op", "")
            handler = _UNDO_DISPATCH.get(op)
            if handler is None:
                log(f"  unknown op {op!r}, skipping")
                counters["skipped"] += 1
                continue
            result = handler(entry)
            log(f"  {result}")
            # Strip the original "op" + "ts" keys from the entry before
            # unpacking so they don't collide with the positional op arg
            # (we're passing "undo_<op>" as the op) and don't overwrite
            # the new record's timestamp.
            echo_fields = {k: v for k, v in entry.items() if k not in ("op", "ts")}
            undo_rb.record("undo_" + op, **echo_fields, result=result)
            if result.startswith("removed") or result.startswith("moved") or result.startswith("recreated"):
                counters["undone"] += 1
            elif result.startswith("skipped"):
                counters["skipped"] += 1
            elif result.startswith("CANNOT"):
                counters["unrecoverable"] += 1
            else:
                counters["failed"] += 1

    log(
        f"Undo complete: {counters['undone']} reversed, "
        f"{counters['skipped']} skipped, "
        f"{counters['failed']} failed, "
        f"{counters['unrecoverable']} unrecoverable."
    )
    return counters
