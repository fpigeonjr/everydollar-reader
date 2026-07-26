# Synthetic export fixtures

Every file in this directory is **fully synthetic**: all merchants, groups,
items, accounts, and amounts were invented for testing. These fixtures contain
**no personal financial information** — no real export rows were copied or
redacted to create them.

The shapes mirror the real EveryDollar export schema recorded in
`docs/scope.md` ("Discovered export schema"):

- UTF-8 with BOM, LF line endings, plain two-decimal amounts, `MM/DD/YYYY`
  dates
- Budget Export headers: `Group, Item, Planned, Spent, Remaining`
- Transaction Export headers, both observed versions:
  - v1 (`05-2026-*`): no `Account` column
  - v2 (`07-2026-*`): adds `Account` between `Merchant` and `Amount`
- Edge shapes: zero-value rows, net-credit (positive `Spent`) items, overspent
  items (negative `Remaining`), fund carryover rows where `Remaining` is not
  derivable from the month alone, exact duplicate transactions, split
  transactions (shared date + merchant), adjacent-prior-month transaction
  dates, and mostly-empty `Note` columns
- Same-month pairs are internally consistent: `Spent` equals the signed sum of
  the month's tracked transactions per item

Filenames follow the observed `MM-YYYY-EveryDollar-<kind>.csv` convention.
