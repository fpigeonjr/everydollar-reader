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
import re
from dataclasses import dataclass
from pathlib import Path

_SNAPSHOT_STEM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class SnapshotRef:
    """A retained snapshot's identity — its month and Snapshot Time.

    ``snapshot_time`` is the ISO-8601 string stored verbatim on disk; callers
    format it for display.
    """

    month: str
    snapshot_time: str

    def display_time(self) -> str:
        """Render ``snapshot_time`` for humans (see :func:`render_snapshot_time`)."""
        return render_snapshot_time(self.snapshot_time)


def _is_snapshot_file(path: Path) -> bool:
    """True when ``path`` is a snapshot file for a ``YYYY-MM`` budget month.

    Matches the documented storage layout (``<YYYY-MM>.json``) and rejects
    other ``.json`` files that may share the data directory, so unrelated
    caches or backups are neither listed nor warned about.
    """
    return path.suffix == ".json" and bool(_SNAPSHOT_STEM_RE.match(path.stem))


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


def render_snapshot_time(value: str) -> str:
    """Render a stored Snapshot Time string for humans.

    Performs no parsing or validation: the first ``T`` in the stored string
    (if any) is replaced with a space so an ISO-8601 timestamp reads
    naturally. Any value is returned through this single substitution, so a
    malformed ``snapshot_time`` is passed through with only that substitution
    applied rather than rejected.
    """
    if "T" in value:
        value = value.replace("T", " ", 1)
    return value


# Budget Export column names as written by ``import`` (see snapshot.py).
_BUDGET_COL = {
    "group": "Group",
    "item": "Item",
    "planned": "Planned",
    "spent": "Spent",
    "remaining": "Remaining",
}


@dataclass(frozen=True)
class ItemRow:
    """One Budget Item row read verbatim from a stored snapshot.

    Amounts are the plain two-decimal strings written on disk; ``remaining``
    is stored verbatim and never derived here (carryover semantics are not
    derivable from a single month's exports — see CONTEXT.md).
    """

    group: str
    item: str
    planned: str
    spent: str
    remaining: str


@dataclass(frozen=True)
class Snapshot:
    """A retained Budget Snapshot's month, Snapshot Time, and Budget Items."""

    month: str
    snapshot_time: str
    items: list[ItemRow]

    def display_time(self) -> str:
        """Render ``snapshot_time`` for humans (see :func:`render_snapshot_time`)."""
        return render_snapshot_time(self.snapshot_time)


def _budget_rows(payload: dict[str, object]) -> list[dict[str, str]]:
    """Return the Budget Export rows from a stored snapshot payload.

    The on-disk shape written by :func:`snapshot.store_snapshot` nests rows
    under ``budget.rows`` with the Budget Export's title-case column names.
    Returns an empty list when the shape is absent or malformed so callers
    can distinguish "no snapshot" from "snapshot with no budget rows".
    """
    budget = payload.get("budget")
    if not isinstance(budget, dict):
        return []
    rows = budget.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _str(value: object) -> str:
    """Return ``value`` as a string, treating ``None`` (a JSON ``null``) as empty.

    ``str(None)`` would otherwise render the literal ``"None"``, which can
    leak into CLI output and make a malformed snapshot look valid.
    """
    return "" if value is None else str(value)


def load_snapshot(data_dir: Path, month: str) -> Snapshot | None:
    """Return the stored snapshot for ``month``, or ``None`` if absent.

    Raises only on filesystem/JSON errors that make the file unreadable; a
    snapshot missing its ``budget.rows`` is returned with an empty item list
    so callers can distinguish "no snapshot" from "snapshot with no budget
    rows".
    """
    path = data_dir / f"{month}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))  # may raise
    snap_month = _str(payload.get("month") or month)
    snapshot_time = _str(payload.get("snapshot_time") or "")
    items = [
        ItemRow(
            group=_str(row.get(_BUDGET_COL["group"])),
            item=_str(row.get(_BUDGET_COL["item"])),
            planned=_str(row.get(_BUDGET_COL["planned"])),
            spent=_str(row.get(_BUDGET_COL["spent"])),
            remaining=_str(row.get(_BUDGET_COL["remaining"])),
        )
        for row in _budget_rows(payload)
    ]
    return Snapshot(month=snap_month, snapshot_time=snapshot_time, items=items)


def load_snapshot_or_warn(
    data_dir: Path, month: str
) -> tuple[Snapshot | None, str | None]:
    """Like :func:`load_snapshot` but never raises.

    Returns ``(snapshot, warning)``. A missing file is ``(None, None)``; an
    unreadable file is ``(None, <human-readable warning>)`` so callers can
    surface corruption without crashing, mirroring :func:`load_snapshots`.
    """
    try:
        return load_snapshot(data_dir, month), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{month}.json: unreadable ({exc.__class__.__name__})"


def latest_month(data_dir: Path) -> str | None:
    """Return the newest ``YYYY-MM`` retained under ``data_dir``, or ``None``.

    Mirrors :func:`load_snapshots`' ordering (ascending by month).
    """
    snapshots, _ = load_snapshots(data_dir)
    return snapshots[-1].month if snapshots else None