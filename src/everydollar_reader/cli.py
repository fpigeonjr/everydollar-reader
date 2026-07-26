"""Command-line interface for EveryDollar Reader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from everydollar_reader import __version__
from everydollar_reader.paths import data_home, ensure_data_home
from everydollar_reader.snapshot import (
    SnapshotImportError,
    build_snapshot,
    store_snapshot,
)
from everydollar_reader.snapshots import (
    ItemRow,
    Snapshot,
    latest_month,
    load_snapshot_or_warn,
    load_snapshots,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="everydollar-reader",
        description=(
            "Read-only CLI for budget snapshots built from user-exported "
            "EveryDollar Budget Export and Transaction Export files."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "Override the data directory "
            f"(default: {data_home()})"
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    import_p = sub.add_parser(
        "import",
        help="Import a same-month Budget Export + Transaction Export pair",
    )
    import_p.add_argument(
        "--month",
        required=True,
        help="Budget month (YYYY-MM) for the export pair",
    )
    import_p.add_argument(
        "--budget",
        type=Path,
        required=True,
        help="Path to the Budget Export file",
    )
    import_p.add_argument(
        "--transactions",
        type=Path,
        required=True,
        help="Path to the Transaction Export file",
    )
    import_p.set_defaults(func=cmd_import)

    status_p = sub.add_parser(
        "status",
        help="List retained budget months and snapshot freshness",
    )
    status_p.set_defaults(func=cmd_status)

    item_p = sub.add_parser(
        "item",
        help="Show planned, spent, and remaining for a Budget Item",
    )
    item_p.add_argument(
        "name",
        help="Budget Item name as it appears in the snapshot",
    )
    item_p.add_argument(
        "--month",
        help="Budget month (YYYY-MM). Defaults to the latest imported month.",
    )
    item_p.set_defaults(func=cmd_item)

    return parser


def _resolve_data_dir(args: argparse.Namespace) -> Path:
    if args.data_dir is not None:
        path = args.data_dir.expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return ensure_data_home()


def cmd_import(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir(args)
    budget = args.budget.expanduser()
    transactions = args.transactions.expanduser()

    try:
        snapshot = build_snapshot(args.month, budget, transactions)
        path = store_snapshot(data_dir, snapshot)
    except SnapshotImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"imported {args.month}: "
        f"{len(snapshot['budget']['rows'])} budget rows, "
        f"{len(snapshot['transactions']['rows'])} transaction rows -> {path}",
        file=sys.stdout,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir(args)
    print(f"data-dir: {data_dir}")
    snapshots, warnings = load_snapshots(data_dir)
    for warning in warnings:
        print(f"warning: {warning}")
    if not snapshots:
        print("No budget snapshots imported yet.")
        return 0
    print(f"{len(snapshots)} budget snapshot(s):")
    for snap in snapshots:
        print(f"  {snap.month}  Snapshot Time: {snap.display_time()}")
    print("Snapshots are point-in-time; EveryDollar may have changed since.")
    return 0


def _find_item(snapshot: Snapshot, name: str) -> ItemRow | None:
    """Case-insensitive exact match on Budget Item name within a snapshot."""
    target = name.casefold()
    for row in snapshot.items:
        if row.item.casefold() == target:
            return row
    return None


def cmd_item(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir(args)

    if args.month:
        month = args.month
    else:
        month = latest_month(data_dir) or ""
    if not month:
        print("No budget snapshots imported yet.")
        return 0

    snapshot, warning = load_snapshot_or_warn(data_dir, month)
    if snapshot is None:
        if warning is not None:
            # Corrupt cache: surface the read failure without crashing,
            # mirroring ``status``. The cache is disposable.
            print(f"warning: {warning}")
            return 0
        refs, _ = load_snapshots(data_dir)
        available = ", ".join(s.month for s in refs) or "none"
        print(f"No snapshot for {month}. Available month(s): {available}.")
        return 0

    row = _find_item(snapshot, args.name)
    if row is None:
        print(
            f"No Budget Item named {args.name!r} in {month}. Available item(s):"
        )
        for entry in snapshot.items:
            print(f"  {entry.item}")
        return 1

    print(f"Budget Item: {row.item}")
    print(f"Group: {row.group}")
    print(f"Planned: {row.planned}")
    print(f"Spent: {row.spent}")
    print(f"Remaining: {row.remaining}")
    print(f"Month: {snapshot.month}")
    print(f"Snapshot Time: {snapshot.display_time()}")
    print("Snapshots are point-in-time; EveryDollar may have changed since.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
