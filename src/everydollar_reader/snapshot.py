"""Parse EveryDollar exports into a replaceable per-month Budget Snapshot.

A Budget Snapshot mirrors one budget month's Budget Export and Transaction
Export faithfully as per-month JSON under the XDG data home. ``Remaining`` is
stored verbatim and never derived; transaction rows carry no synthesized IDs.

All validation happens before any file is written, so a malformed input never
leaves a partial snapshot on disk. Diagnostics are structural only (row
counts and headers); merchants, amounts, and names are never logged.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

BUDGET_HEADERS = ["Group", "Item", "Planned", "Spent", "Remaining"]
TXN_HEADERS_V1 = ["Group", "Item", "Type", "Date", "Merchant", "Amount", "Note"]
TXN_HEADERS_V2 = [
    "Group",
    "Item",
    "Type",
    "Date",
    "Merchant",
    "Account",
    "Amount",
    "Note",
]
TXN_HEADER_VERSIONS = [TXN_HEADERS_V2, TXN_HEADERS_V1]

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
# Observed EveryDollar filename convention: "MM-YYYY-EveryDollar-<kind>.csv".
_FILENAME_RE = re.compile(r"^(\d{2})-(\d{4})-EveryDollar-", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"^-?\d+\.\d{2}$")
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


class SnapshotImportError(Exception):
    """Raised when an export pair cannot form a valid Budget Snapshot."""


def _now() -> datetime:
    return datetime.now().astimezone()


def _validate_month(month: str) -> str:
    if not _MONTH_RE.match(month):
        raise SnapshotImportError(
            f"invalid --month {month!r}: expected YYYY-MM (e.g. 2026-07)"
        )
    return month


def _filename_month(path: Path) -> str | None:
    """Return the YYYY-MM implied by the EveryDollar filename convention.

    Returns ``None`` when the basename does not match the observed
    ``MM-YYYY-EveryDollar-*`` convention, so the caller only enforces
    agreement when the convention actually applies.
    """
    match = _FILENAME_RE.match(path.name)
    if not match:
        return None
    mm, yyyy = match.group(1), match.group(2)
    return f"{yyyy}-{mm}"


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except FileNotFoundError as exc:
        raise SnapshotImportError(f"export file not found: {path}") from exc
    except OSError as exc:
        raise SnapshotImportError(f"could not read {path}: {exc}") from exc
    return list(headers), rows


def _row_value(row: dict[str, Any], col: str) -> str:
    """Return a cell as a string, treating ``csv.DictReader``'s ``None``
    (missing or blank field) as the empty string so regex checks raise a
    clear ``SnapshotImportError`` instead of ``TypeError``."""
    return row.get(col) or ""


def _reject_extra_columns(row: dict[str, Any], kind: str) -> None:
    """``csv.DictReader`` stores fields beyond the header row under a ``None``
    key. Reject them so extra data is never silently serialized."""
    if None in row:
        raise SnapshotImportError(
            f"{kind} row has more columns than its header"
        )


def _validate_budget(headers: list[str], rows: list[dict[str, str]]) -> None:
    if headers != BUDGET_HEADERS:
        raise SnapshotImportError(
            "Budget Export headers must be "
            f"{','.join(BUDGET_HEADERS)}; got {','.join(headers) or '<empty>'}"
        )
    for row in rows:
        _reject_extra_columns(row, "Budget Export")
        for col in ("Planned", "Spent", "Remaining"):
            if not _AMOUNT_RE.match(_row_value(row, col)):
                raise SnapshotImportError(
                    f"Budget Export row has invalid {col}: must be a plain "
                    "two-decimal amount (e.g. -12.34)"
                )


def _validate_transactions(
    headers: list[str], rows: list[dict[str, str]]
) -> None:
    if headers not in TXN_HEADER_VERSIONS:
        raise SnapshotImportError(
            "Transaction Export headers must be v1 "
            f"({','.join(TXN_HEADERS_V1)}) or v2 ({','.join(TXN_HEADERS_V2)}); "
            f"got {','.join(headers) or '<empty>'}"
        )
    for row in rows:
        _reject_extra_columns(row, "Transaction Export")
        if not _DATE_RE.match(_row_value(row, "Date")):
            raise SnapshotImportError(
                "Transaction Export row has invalid Date: expected MM/DD/YYYY"
            )
        if not _AMOUNT_RE.match(_row_value(row, "Amount")):
            raise SnapshotImportError(
                "Transaction Export row has invalid Amount: must be a plain "
                "two-decimal amount (e.g. -12.34)"
            )


def _check_filename_agreement(month: str, *paths: Path) -> None:
    for path in paths:
        implied = _filename_month(path)
        if implied is not None and implied != month:
            raise SnapshotImportError(
                f"{path.name} implies month {implied} but --month is {month}"
            )


def build_snapshot(
    month: str,
    budget_path: Path,
    transactions_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate an export pair and return the in-memory Budget Snapshot.

    Raises :class:`SnapshotImportError` on any problem. Touches no files.
    """
    _validate_month(month)
    b_headers, b_rows = _load_rows(budget_path)
    t_headers, t_rows = _load_rows(transactions_path)
    _check_filename_agreement(month, budget_path, transactions_path)
    _validate_budget(b_headers, b_rows)
    _validate_transactions(t_headers, t_rows)

    snapshot_time = (now or _now()).isoformat(timespec="seconds")
    return {
        "schema_version": SCHEMA_VERSION,
        "month": month,
        "snapshot_time": snapshot_time,
        "budget": {"headers": b_headers, "rows": b_rows},
        "transactions": {"headers": t_headers, "rows": t_rows},
    }


def store_snapshot(data_dir: Path, snapshot: dict[str, Any]) -> Path:
    """Write a Budget Snapshot to ``<data_dir>/<month>.json``, replacing any
    existing snapshot for that month.

    ``snapshot`` is assumed to have been built (and validated) by
    :func:`build_snapshot`. As a path-traversal guard, ``month`` is re-validated
    here before it is used in a filename. Writes via a temp file + atomic
    replace so a partial snapshot is never left on disk."""
    month = snapshot["month"]
    _validate_month(month)
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"{month}.json"
    tmp = data_dir / f".{month}.json.tmp"
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target