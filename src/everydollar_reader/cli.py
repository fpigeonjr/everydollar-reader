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

_SCHEMA_GATE = (
    "not implemented: parser work waits on same-month export schema discovery "
    "and synthetic fixtures (see docs/scope.md and GitHub issues #2–#3)"
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
    print("No budget snapshots imported yet.")
    return 0


def cmd_item(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir(args)
    month = args.month or "latest"
    print(
        f"data-dir: {data_dir}\n"
        f"item: {args.name}\n"
        f"month: {month}\n"
        f"error: {_SCHEMA_GATE}",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
