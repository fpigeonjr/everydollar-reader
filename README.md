# EveryDollar Reader

EveryDollar Reader is a planned local, read-only **CLI** for querying budget and
tracked-transaction data that a user explicitly downloads from EveryDollar.
Its first consumer will be the Accountant Area Agent in a personal Hermes
installation, which will shell out to this CLI rather than using a dedicated
MCP server.

The project is in discovery. It does not yet parse exports or provide commands.

## Product boundary

- EveryDollar remains the system of record.
- Imports are manual, normally weekly and on demand.
- The reader never signs in to EveryDollar and never creates, categorizes,
  moves, splits, or deletes upstream records.
- Local history is a disposable cache, initially containing all available
  months and growing toward a rolling 13-month window.
- Raw data is available only to the Accountant Area Agent by normal Hermes
  profile and tool boundaries. This is operational isolation, not hard
  isolation from other processes running as the same macOS user.

See [CONTEXT.md](./CONTEXT.md) for canonical domain language and
[docs/scope.md](./docs/scope.md) for the current discovery record.

## Data safety

Real exports, financial databases, credentials, and generated snapshots must
not be committed. The repository ignores these by default. Future tests must
use synthetic fixtures reviewed to ensure that they contain no personal
financial information.

## Public-release status

The scaffold is public at
[github.com/fpigeonjr/everydollar-reader](https://github.com/fpigeonjr/everydollar-reader).
A usable public release still waits on export-schema discovery, synthetic
fixtures, and privacy checks. The public project name is not final.

EveryDollar is a trademark of Ramsey Solutions. This project is unofficial and
is not affiliated with or endorsed by Ramsey Solutions.
