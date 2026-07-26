# Budget Reading

This context describes a read-only view of a person's EveryDollar budget for
use by their Accountant Area Agent.

## Language

**Budget Reader**:
The local read-only view of budget information supplied through explicit EveryDollar exports.
_Avoid_: EveryDollar API, scraper, sync service

**EveryDollar Budget**:
The authoritative monthly budget maintained by the user in EveryDollar.
_Avoid_: Local budget, reader database

**Budget Snapshot**:
A point-in-time representation of one budget month formed from its Budget Export and Transaction Export.
_Avoid_: Sync, backup, transaction snapshot

**Budget Export**:
The user-requested EveryDollar download representing budget-item state for one month.
_Avoid_: Budget snapshot, transaction export

**Transaction Export**:
The user-requested EveryDollar download containing transactions tracked to one month's budget.
_Avoid_: Bank statement, budget export

**Tracked Transaction**:
A transaction assigned to at least one Budget Item in EveryDollar.
_Avoid_: Pending transaction, bank transaction

**Budget Group**:
A named collection of related Budget Items within an EveryDollar Budget.
_Avoid_: Category

**Budget Item**:
A named planning and tracking line within a Budget Group.
_Avoid_: Category, transaction

**Snapshot Time**:
The time at which the user downloaded the exports represented by a Budget Snapshot.
_Avoid_: Transaction date, import time

**Accountant**:
The Hermes Area Agent that may inspect raw Budget Snapshots and answer finance questions for Frank.
_Avoid_: Main agent, financial adviser

**Budget Reader CLI**:
The local command-line interface the Accountant shells out to for import status and read-only budget queries.
_Avoid_: MCP server, API service, EveryDollar client

## Relationships

- An **EveryDollar Budget** is the authority for exactly one budget month
- A **Budget Snapshot** represents exactly one **EveryDollar Budget** at one **Snapshot Time**
- A **Budget Snapshot** contains exactly one **Budget Export** and one **Transaction Export**
- A **Budget Group** contains one or more **Budget Items**
- A **Tracked Transaction** belongs to one budget month and is assigned to one or more **Budget Items**
- The **Accountant** may inspect raw **Budget Snapshots** through the **Budget Reader CLI**

## Example dialogue

> **Frank:** "How much remains for dining?"
> **Accountant:** "The latest **Budget Snapshot** shows the dining **Budget Item** as of its **Snapshot Time**. It may not include changes made in the **EveryDollar Budget** since then."

## Flagged ambiguities

- "API access" originally meant direct access to EveryDollar; resolved: the **Budget Reader** reads explicit exports and does not access EveryDollar directly.
- "snapshot" was used for a transaction CSV alone; resolved: a **Budget Snapshot** requires both the month's **Budget Export** and **Transaction Export**.
- "category" can mean either a **Budget Group** or **Budget Item**; resolved: use the more precise EveryDollar term.
- "remaining" may mean arithmetic planned-minus-spent or EveryDollar's safe-to-spend presentation; unresolved until representative Budget Export schemas are inspected.
