---
type: community
cohesion: 0.29
members: 7
---

# Pending Transactions & Fintoc

**Cohesion:** 0.29 - loosely connected
**Members:** 7 nodes

## Members
- [[API DELETE transactions{id}]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[API GET transactionspending]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[Feature Pending Transactions Block + Reconciliation]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[Module backendmodulesfintoc]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[Rationale Cross-sender dedup for Banco de Chile email pairs]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[Transaction Reconciliation + Pending Block Plan]] - document - docs/superpowers/plans/2026-03-24-transaction-reconciliation.md
- [[Transaction Reconciliation Design Spec]] - document - docs/superpowers/specs/2026-03-24-transaction-reconciliation-design.md

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Pending_Transactions_&_Fintoc
SORT file.name ASC
```
