# Discovery Scope

Status: repository scaffold; schema discovery pending.

## Goal

Give Frank's Accountant Area Agent deterministic, read-only access to budget
and tracked-transaction history that Frank explicitly exports from
EveryDollar.

The first useful questions are:

- What was planned, spent, and remaining for a budget item at the latest
  snapshot?
- Which recent transactions or spending patterns are unusual?
- How does spending compare across available months?

Every answer based on a snapshot must expose or account for its freshness.

## Resolved decisions

| Decision | Current boundary |
| --- | --- |
| Upstream access | User-requested downloads only |
| Mutation | No upstream writes |
| Import cadence | Weekly and on demand |
| Snapshot contents | Same-month budget and tracked-transaction exports |
| System of record | EveryDollar |
| Local state | Disposable derived cache |
| History | Import all available months from January 2026 onward; grow toward a rolling 13 months |
| Raw-data consumer | Accountant Area Agent only |
| Isolation strength | Operational profile/tool isolation; no separate OS identity |
| Public release | Deferred until synthetic fixtures and privacy checks exist |

## Explicit non-goals

- Logging in to EveryDollar
- Browser automation, scraping, or reverse-engineering private endpoints
- Creating, editing, categorizing, moving, splitting, or deleting transactions
- Replacing EveryDollar as the budget authority
- Making financial decisions autonomously
- Committing or publishing real financial exports
- Providing raw budget access to the main Hermes session or other Area Agents

## Data-safety rules

1. Real exports and derived databases stay outside git.
2. Logs contain structural diagnostics, never rows, merchants, category names,
   or amounts.
3. Tests use synthetic, privacy-reviewed fixtures.
4. Tool responses return only the data needed for the user's question.
5. Snapshot-based answers identify the effective snapshot time.

## Schema-discovery gate

Parser implementation begins only after representative exports from the same
month are available for local inspection. Inspection must establish:

- Exact headers, encodings, numeric formats, and date formats
- How planned, spent, and remaining values are represented
- How income, expenses, funds, goals, and zero-value items appear
- Whether split transactions have stable identities
- How empty exports, duplicated downloads, and revised snapshots behave

Real rows will not become fixtures. Once the shapes are understood, equivalent
synthetic fixtures will be authored.

## Open design questions

- What normalized model faithfully represents the observed export schemas?
- How should repeated imports of a revised month replace or version a snapshot?
- Which deterministic queries belong in the first Accountant-facing tool?
- Should the local interface be a CLI, an MCP server, or both?
- What brand-neutral name should be used if the project becomes public?
