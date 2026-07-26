"""Validation suite for the synthetic export fixtures.

The fixtures under tests/fixtures/ model the real EveryDollar export shapes
recorded in docs/scope.md ("Discovered export schema"). These tests pin both
the file-level contract (encoding, headers, formats) and the edge shapes the
parser must tolerate, so fixture drift fails loudly.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
BUDGET_07 = FIXTURES / "07-2026-EveryDollar-BudgetItems.csv"
TXNS_07 = FIXTURES / "07-2026-EveryDollar-Transactions.csv"
BUDGET_05 = FIXTURES / "05-2026-EveryDollar-BudgetItems.csv"
TXNS_05 = FIXTURES / "05-2026-EveryDollar-Transactions.csv"

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


def load_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_budget_fixture_exists_with_export_headers() -> None:
    assert BUDGET_07.is_file()
    with open(BUDGET_07, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        assert next(reader) == BUDGET_HEADERS


ALL_CSVS = [BUDGET_07, TXNS_07, BUDGET_05, TXNS_05]


@pytest.mark.parametrize("path", ALL_CSVS, ids=lambda p: p.name)
def test_fixtures_use_bom_and_lf_endings(path: Path) -> None:
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
    assert b"\r" not in raw, "unexpected CR line endings"


AMOUNT_RE = re.compile(r"^-?\d+\.\d{2}$")


def test_budget_amounts_are_plain_two_decimal() -> None:
    for row in load_rows(BUDGET_07):
        for col in ("Planned", "Spent", "Remaining"):
            assert AMOUNT_RE.match(row[col]), f"{col}={row[col]!r}"


def test_budget_items_are_unique() -> None:
    items = [row["Item"] for row in load_rows(BUDGET_07)]
    assert len(items) == len(set(items))


def test_budget_fixture_has_zero_values_in_every_amount_column() -> None:
    rows = load_rows(BUDGET_07)
    for col in ("Planned", "Spent", "Remaining"):
        assert any(Decimal(row[col]) == 0 for row in rows), f"no zero {col}"


def test_budget_fixture_has_credit_and_overspend_shapes() -> None:
    rows = load_rows(BUDGET_07)
    # A net-credit item: positive Spent (refunds exceed spending).
    assert any(Decimal(row["Spent"]) > 0 for row in rows)
    # Overspent / over-received items: negative Remaining.
    assert any(Decimal(row["Remaining"]) < 0 for row in rows)


def test_budget_fixture_has_carryover_rows_not_derivable_from_the_month() -> None:
    rows = load_rows(BUDGET_07)
    # Fund-style rows whose Remaining includes a carried balance, matching
    # neither Planned + Spent nor Planned - Spent.
    carryover = [
        row
        for row in rows
        if Decimal(row["Remaining"]) != Decimal(row["Planned"]) + Decimal(row["Spent"])
        and Decimal(row["Remaining"]) != Decimal(row["Planned"]) - Decimal(row["Spent"])
    ]
    assert carryover, "no carryover-shaped rows"


DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def test_transaction_fixture_v2_exists_with_account_column() -> None:
    assert TXNS_07.is_file()
    with open(TXNS_07, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        assert next(reader) == TXN_HEADERS_V2


def test_transaction_amounts_and_dates_match_export_formats() -> None:
    for row in load_rows(TXNS_07):
        assert AMOUNT_RE.match(row["Amount"]), f"Amount={row['Amount']!r}"
        assert DATE_RE.match(row["Date"]), f"Date={row['Date']!r}"
        datetime.strptime(row["Date"], "%m/%d/%Y")


TXN_TYPES = {"debt", "expense", "fund", "income"}


def test_transaction_types_cover_the_full_vocabulary() -> None:
    types = {row["Type"] for row in load_rows(TXNS_07)}
    assert types == TXN_TYPES


def test_transaction_sign_conventions_by_type() -> None:
    rows = load_rows(TXNS_07)
    expenses = [Decimal(r["Amount"]) for r in rows if r["Type"] == "expense"]
    income = [Decimal(r["Amount"]) for r in rows if r["Type"] == "income"]
    debt = [Decimal(r["Amount"]) for r in rows if r["Type"] == "debt"]
    fund = [Decimal(r["Amount"]) for r in rows if r["Type"] == "fund"]
    # Expenses are predominantly negative, with refunds stored positive.
    assert sum(a < 0 for a in expenses) > sum(a > 0 for a in expenses) > 0
    assert income and all(a > 0 for a in income)
    assert debt and all(a < 0 for a in debt)
    # Fund movements go both ways (contributions out, withdrawals in).
    assert any(a < 0 for a in fund) and any(a > 0 for a in fund)


def test_transaction_fixture_has_exact_duplicate_rows() -> None:
    keys = [tuple(row.values()) for row in load_rows(TXNS_07)]
    assert len(keys) != len(set(keys)), "no exact duplicate rows"


def test_transaction_fixture_has_split_rows_sharing_date_and_merchant() -> None:
    rows = load_rows(TXNS_07)
    pairs = {(row["Date"], row["Merchant"]) for row in rows}
    splits = [
        pair
        for pair in pairs
        if len({row["Amount"] for row in rows if (row["Date"], row["Merchant"]) == pair})
        > 1
    ]
    assert splits, "no split-shaped rows"


def test_transaction_fixture_has_adjacent_prior_month_dates() -> None:
    months = {row["Date"][:2] for row in load_rows(TXNS_07)}
    assert months == {"06", "07"}


def test_transaction_notes_are_mostly_empty() -> None:
    rows = load_rows(TXNS_07)
    populated = sum(bool(row["Note"]) for row in rows)
    assert 0 < populated <= len(rows) // 4


def assert_pair_consistent(budget: Path, txns: Path) -> None:
    """Transaction vocabulary is a subset of the budget's, and Spent is the
    signed sum of the month's tracked transactions per item."""
    budget_rows = load_rows(budget)
    txn_rows = load_rows(txns)
    assert {(row["Group"], row["Item"]) for row in txn_rows} <= {
        (row["Group"], row["Item"]) for row in budget_rows
    }
    sums: dict[tuple[str, str], Decimal] = {}
    for row in txn_rows:
        key = (row["Group"], row["Item"])
        sums[key] = sums.get(key, Decimal(0)) + Decimal(row["Amount"])
    for row in budget_rows:
        key = (row["Group"], row["Item"])
        assert Decimal(row["Spent"]) == sums.get(key, Decimal(0)), key


def test_july_pair_is_internally_consistent() -> None:
    assert_pair_consistent(BUDGET_07, TXNS_07)


def test_budget_fixture_has_a_zero_activity_item() -> None:
    active = {(row["Group"], row["Item"]) for row in load_rows(TXNS_07)}
    inactive = [
        row["Item"]
        for row in load_rows(BUDGET_07)
        if (row["Group"], row["Item"]) not in active
    ]
    assert inactive, "no zero-activity budget items"


def test_transaction_fixture_v1_exists_without_account_column() -> None:
    assert TXNS_05.is_file()
    with open(TXNS_05, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        assert next(reader) == TXN_HEADERS_V1


def test_may_pair_uses_the_same_formats() -> None:
    for row in load_rows(BUDGET_05):
        for col in ("Planned", "Spent", "Remaining"):
            assert AMOUNT_RE.match(row[col]), f"{col}={row[col]!r}"
    for row in load_rows(TXNS_05):
        assert AMOUNT_RE.match(row["Amount"]), f"Amount={row['Amount']!r}"
        assert DATE_RE.match(row["Date"]), f"Date={row['Date']!r}"


def test_may_pair_is_internally_consistent() -> None:
    assert_pair_consistent(BUDGET_05, TXNS_05)


def test_fixtures_readme_declares_no_personal_data() -> None:
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8").lower()
    assert "synthetic" in readme
    assert "no personal" in readme
