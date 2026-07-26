"""Read-side access to retained Budget Snapshots.

A Budget Snapshot for one budget month is stored as a per-month JSON file
under the data home (see :mod:`everydollar_reader.paths`). This module is the
single reader of that on-disk cache: a small interface over the on-disk
layout so that ``import`` (issue #4) can write the same shape later without
callers here changing.

The cache is disposable; malformed files are surfaced as warnings rather
than raised, and never crash a status read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotRef:
    """A retained snapshot's identity — its month and Snapshot Time.

    ``snapshot_time`` is the ISO-8601 string stored verbatim on disk; callers
    format it for display.
    """

    month: str
    snapshot_time: str

    def display_time(self) -> str:
        """Render ``snapshot_time`` for humans.

        Accepts any ISO-8601 timestamp; returns the precision provided on disk
        with the ``T`` date/time separator replaced by a space. Unknown or
        non-ISO values are returned unchanged so a bad file never crashes a
        status read.
        """
        value = self.snapshot_time
        if "T" in value:
            value = value.replace("T", " ", 1)
        return value


def _is_snapshot_file(path: Path) -> bool:
    return path.suffix == ".json" and path.stem[:1].isdigit() and "-" in path.stem


def load_snapshots(data_dir: Path) -> tuple[list[SnapshotRef], list[str]]:
    """Return ``(snapshots, warnings)`` for every valid snapshot in ``data_dir``.

    Snapshots are ordered by month ascending; snapshot files that fail to
    parse or are missing required fields contribute a human-readable warning
    instead of raising.
    """
    snapshots: list[SnapshotRef] = []
    warnings: list[str] = []
    if not data_dir.is_dir():
        return snapshots, warnings
    for path in sorted(data_dir.iterdir()):
        if not _is_snapshot_file(path):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path.name}: unreadable ({exc.__class__.__name__})")
            continue
        month = payload.get("month") or path.stem
        snapshot_time = payload.get("snapshot_time")
        if not snapshot_time:
            warnings.append(f"{path.name}: missing snapshot_time")
            continue
        snapshots.append(SnapshotRef(month=month, snapshot_time=snapshot_time))
    snapshots.sort(key=lambda s: s.month)
    return snapshots, warnings