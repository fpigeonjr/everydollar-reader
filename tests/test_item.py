"""Behavior tests for ``everydollar-reader item``.

Snapshots are populated through the real ``import`` storage path
(``build_snapshot`` + ``store_snapshot`` from issue #4) against the synthetic
fixtures under ``tests/fixtures`` (issue #3), so ``item`` is verified against
the exact on-disk shape that ``import`` writes. No real financial data is used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from everydollar_reader.cli import main
from everydollar_reader.snapshot import build_snapshot, store_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
BUDGET_07 = FIXTURES / "07-2026-EveryDollar-BudgetItems.csv"
TXNS_07 = FIXTURES / "07-2026-EveryDollar-Transactions.csv"
BUDGET_05 = FIXTURES / "05-2026-EveryDollar-BudgetItems.csv"
TXNS_05 = FIXTURES / "05-2026-EveryDollar-Transactions.csv"

# Fixed Snapshot Times so assertions are deterministic.
JULY_TIME = "2026-07-26T14:03:00+00:00"
MAY_TIME = "2026-05-12T09:10:00+00:00"


def _import(
    data_dir: Path,
    month: str,
    budget: Path,
    transactions: Path,
    snapshot_time: str,
) -> None:
    """Write a retained snapshot for ``month`` via the real import path."""
    snap = build_snapshot(
        month,
        budget,
        transactions,
        now=datetime.fromisoformat(snapshot_time),
    )
    store_snapshot(data_dir, snap)


def _july_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    _import(data_dir, "2026-07", BUDGET_07, TXNS_07, JULY_TIME)
    return data_dir


# A Budget Item whose Remaining is carryover (not Planned+/-Spent), taken from
# the July fixture: Planned 100.00, Spent -100.00, Remaining 850.00.
CARRYOVER_ITEM = "Emergency Fund"
CARRYOVER_REMAINING = "850.00"


def test_item_reports_planned_spent_remaining_and_snapshot_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = _july_data_dir(tmp_path)

    code = main(["--data-dir", str(data_dir), "item", "Restaurants"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Restaurants" in out
    assert "Planned: 120.00" in out
    assert "Spent: 23.50" in out
    assert "Remaining: 143.50" in out
    # Snapshot Time is always identified for a snapshot-based answer.
    assert "Snapshot Time:" in out
    assert "2026-07-26 14:03" in out
    assert "T14:03" not in out


def test_item_defaults_to_latest_month_when_no_month_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    _import(data_dir, "2026-05", BUDGET_05, TXNS_05, MAY_TIME)
    _import(data_dir, "2026-07", BUDGET_07, TXNS_07, JULY_TIME)

    # No --month: resolves to the latest retained month (2026-07), not May.
    # Coffee Shops exists in both months with distinct Planned values
    # (May 35.00, July 40.00), so the echoed Planned proves which month.
    code = main(["--data-dir", str(data_dir), "item", "Coffee Shops"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Month: 2026-07" in out
    assert "Planned: 40.00" in out  # July Planned, not May's 35.00
    assert MAY_TIME not in out


def test_item_month_flag_selects_that_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    _import(data_dir, "2026-05", BUDGET_05, TXNS_05, MAY_TIME)
    _import(data_dir, "2026-07", BUDGET_07, TXNS_07, JULY_TIME)

    code = main(["--data-dir", str(data_dir), "item", "Coffee Shops", "--month", "2026-05"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Month: 2026-05" in out
    assert "Planned: 35.00" in out  # May Planned, not July's 40.00
    assert JULY_TIME not in out


def test_item_match_is_case_insensitive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = _july_data_dir(tmp_path)

    code = main(["--data-dir", str(data_dir), "item", "restaurants"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Budget Item: Restaurants" in out  # canonical name echoed
    assert "Planned: 120.00" in out


def test_item_no_match_lists_available_item_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = _july_data_dir(tmp_path)

    code = main(["--data-dir", str(data_dir), "item", "Dining"])

    assert code == 1  # distinct from "no snapshots" (exit 0)
    out = capsys.readouterr().out
    assert "Dining" in out  # the requested name is echoed
    # Every available item name is listed so the Accountant can retry.
    assert "Restaurants" in out
    assert "Emergency Fund" in out
    assert "Coffee Shops" in out
    # No Planned/Spent/Remaining row is fabricated for a missing item.
    assert "Planned:" not in out


def test_item_no_snapshots_reports_empty_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    code = main(["--data-dir", str(data_dir), "item", "Restaurants"])

    assert code == 0  # readable state, not an error
    out = capsys.readouterr().out
    assert "No budget snapshots imported yet." in out
    assert "Restaurants" not in out


def test_item_requested_month_not_present_lists_available_months(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    _import(data_dir, "2026-05", BUDGET_05, TXNS_05, MAY_TIME)
    _import(data_dir, "2026-07", BUDGET_07, TXNS_07, JULY_TIME)

    code = main(["--data-dir", str(data_dir), "item", "Restaurants", "--month", "2026-03"])

    assert code == 0  # readable state, not an error
    out = capsys.readouterr().out
    assert "2026-03" in out  # the requested month is named
    assert "2026-05" in out and "2026-07" in out  # available months surfaced
    # No row is fabricated for the missing month.
    assert "Planned:" not in out


def test_item_remaining_is_reported_verbatim_not_derived_for_carryover(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = _july_data_dir(tmp_path)

    # Emergency Fund: Planned 100.00, Spent -100.00, Remaining 850.00.
    # Planned + Spent == 0.00 and Planned - Spent == 200.00 — neither equals
    # 850.00, so a derived value would betray the carryover semantics.
    code = main(["--data-dir", str(data_dir), "item", CARRYOVER_ITEM])

    assert code == 0
    out = capsys.readouterr().out
    remaining_line = next(
        ln for ln in out.splitlines() if ln.startswith("Remaining:")
    )
    remaining_value = remaining_line.split(":", 1)[1].strip()
    assert remaining_value == CARRYOVER_REMAINING
    # Planned and Spent are echoed verbatim too.
    assert "Planned: 100.00" in out
    assert "Spent: -100.00" in out


def test_item_output_identifies_snapshot_time_and_point_in_time_disclaimer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = _july_data_dir(tmp_path)

    code = main(["--data-dir", str(data_dir), "item", "Restaurants"])

    assert code == 0
    out = capsys.readouterr().out
    # Snapshot Time identified and rendered readably (ISO ``T`` -> space).
    assert "2026-07-26 14:03" in out
    assert "T14:03" not in out
    # The point-in-time disclaimer is surfaced on every snapshot-based answer.
    assert "point-in-time" in out
    assert "EveryDollar may have changed since" in out