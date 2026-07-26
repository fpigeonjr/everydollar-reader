"""Behavior tests for `import` storing a replaceable Budget Snapshot.

All inputs derive from the synthetic fixtures under ``tests/fixtures`` (issue
#3) or temporary directories. No real financial data is used.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
BUDGET_07 = FIXTURES / "07-2026-EveryDollar-BudgetItems.csv"
TXNS_07 = FIXTURES / "07-2026-EveryDollar-Transactions.csv"
BUDGET_05 = FIXTURES / "05-2026-EveryDollar-BudgetItems.csv"
TXNS_05 = FIXTURES / "05-2026-EveryDollar-Transactions.csv"

EXPECTED_BUDGET_HEADERS = ["Group", "Item", "Planned", "Spent", "Remaining"]
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
TXN_HEADERS_V1 = [
    "Group",
    "Item",
    "Type",
    "Date",
    "Merchant",
    "Amount",
    "Note",
]


def _snapshot_path(data_dir: Path, month: str) -> Path:
    return data_dir / f"{month}.json"


def test_import_stores_snapshot_for_the_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"

    code = _run_import(
        data_dir=data_dir,
        month="2026-07",
        budget=BUDGET_07,
        transactions=TXNS_07,
    )

    assert code == 0, capsys.readouterr().err
    snapshot_file = _snapshot_path(data_dir, "2026-07")
    assert snapshot_file.is_file(), "snapshot JSON was not written under the data home"
    snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))

    assert snapshot["month"] == "2026-07"
    assert snapshot["schema_version"] == 1
    assert snapshot["snapshot_time"]
    assert snapshot["budget"]["headers"] == EXPECTED_BUDGET_HEADERS
    assert snapshot["transactions"]["headers"] == TXN_HEADERS_V2
    # Row counts match the fixtures (no rows dropped or synthesized).
    assert len(snapshot["budget"]["rows"]) == _count_data_rows(BUDGET_07)
    assert len(snapshot["transactions"]["rows"]) == _count_data_rows(TXNS_07)
    # Remaining is stored verbatim, never derived.
    july_rent = next(
        r for r in snapshot["budget"]["rows"] if r["Item"] == "Rent"
    )
    assert july_rent["Remaining"] == "0.00"


def _count_data_rows(path: Path) -> int:
    import csv

    with open(path, newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_reimporting_a_month_overwrites_and_advances_snapshot_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from everydollar_reader import snapshot as snap_mod
    from datetime import datetime, timezone, timedelta

    tz = timezone(timedelta(hours=-4))
    fake_clock = iter(
        [
            datetime(2026, 7, 28, 9, 0, 0, tzinfo=tz),
            datetime(2026, 7, 28, 21, 30, 0, tzinfo=tz),
        ]
    )
    monkeypatch.setattr(
        snap_mod, "_now", lambda: next(fake_clock), raising=True
    )

    data_dir = tmp_path / "data"
    assert _run_import(data_dir, "2026-07", BUDGET_07, TXNS_07) == 0
    first = json.loads(_snapshot_path(data_dir, "2026-07").read_text("utf-8"))

    # The same month imported again must replace, not duplicate or version.
    assert _run_import(data_dir, "2026-07", BUDGET_07, TXNS_07) == 0
    snapshots = list(data_dir.glob("*.json"))
    assert {p.name for p in snapshots} == {"2026-07.json"}
    second = json.loads(_snapshot_path(data_dir, "2026-07").read_text("utf-8"))

    assert second["snapshot_time"] > first["snapshot_time"]
    assert second["budget"]["rows"] == first["budget"]["rows"]
    assert second["transactions"]["rows"] == first["transactions"]["rows"]


def test_transaction_export_v1_without_account_imports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"

    code = _run_import(data_dir, "2026-05", BUDGET_05, TXNS_05)

    assert code == 0, capsys.readouterr().err
    snapshot = json.loads(_snapshot_path(data_dir, "2026-05").read_text("utf-8"))
    assert snapshot["transactions"]["headers"] == TXN_HEADERS_V1
    assert len(snapshot["budget"]["rows"]) == _count_data_rows(BUDGET_05)
    assert len(snapshot["transactions"]["rows"]) == _count_data_rows(TXNS_05)


def test_filename_month_disagreement_fails_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    mismatched_budget = _copy_fixture(
        BUDGET_07, tmp_path / "08-2026-EveryDollar-BudgetItems.csv"
    )

    code = _run_import(data_dir, "2026-07", mismatched_budget, TXNS_07)

    assert code != 0
    err = capsys.readouterr().err
    assert "08-2026" in err
    assert "2026-07" in err
    assert not _snapshot_path(data_dir, "2026-07").is_file()
    assert not any(data_dir.glob("*.json"))


def test_non_conventional_filename_with_matching_month_imports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The filename convention does not apply, so --month is trusted.
    budget = _copy_fixture(BUDGET_07, tmp_path / "budget.csv")
    tx = _copy_fixture(TXNS_07, tmp_path / "tx.csv")
    data_dir = tmp_path / "data"

    code = _run_import(data_dir, "2026-07", budget, tx)

    assert code == 0, capsys.readouterr().err
    assert _snapshot_path(data_dir, "2026-07").is_file()


def test_malformed_budget_amount_fails_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    budget = tmp_path / "budget.csv"
    budget.write_text(
        "\ufeffGroup,Item,Planned,Spent,Remaining\n"
        "Food,Groceries,500.00,-4.7,29.23\n",  # one-decimal Spent
        encoding="utf-8",
    )
    tx = _copy_fixture(TXNS_07, tmp_path / "07-2026-EveryDollar-Transactions.csv")

    code = _run_import(data_dir, "2026-07", budget, tx)

    assert code != 0
    err = capsys.readouterr().err
    assert "Spent" in err or "Amount" in err
    assert not _snapshot_path(data_dir, "2026-07").is_file()


def test_malformed_transaction_date_fails_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    budget = _copy_fixture(
        BUDGET_07, tmp_path / "07-2026-EveryDollar-BudgetItems.csv"
    )
    tx = tmp_path / "07-2026-EveryDollar-Transactions.csv"
    tx.write_text(
        "\ufeffGroup,Item,Type,Date,Merchant,Account,Amount,Note\n"
        "Food,Groceries,expense,2026-07-03,Corner Market,Acct,-82.14,\n",
        encoding="utf-8",
    )

    code = _run_import(data_dir, "2026-07", budget, tx)

    assert code != 0
    err = capsys.readouterr().err
    assert "Date" in err
    assert not _snapshot_path(data_dir, "2026-07").is_file()


def test_bad_month_flag_fails_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"

    code = _run_import(data_dir, "2026-7", BUDGET_07, TXNS_07)

    assert code != 0
    err = capsys.readouterr().err
    assert "YYYY-MM" in err
    assert not _snapshot_path(data_dir, "2026-7").is_file()
    assert not any(data_dir.glob("*.json"))


def _run_import(
    data_dir: Path, month: str, budget: Path, transactions: Path
) -> int:
    from everydollar_reader.cli import main

    return main(
        [
            "--data-dir",
            str(data_dir),
            "import",
            "--month",
            month,
            "--budget",
            str(budget),
            "--transactions",
            str(transactions),
        ]
    )


# --- helpers used by later tests -------------------------------------------------

def _copy_fixture(src: Path, dest: Path) -> Path:
    """Copy a synthetic fixture to a temp path so tests can rename it."""
    shutil.copyfile(src, dest)
    return dest