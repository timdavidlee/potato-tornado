# Collections inventory

A snapshot of the built-in data collections: table count, realism status, scenario
coverage, and field-enrichment backlog state. Per-collection detail lives in each
package's `realism-log.md` (history + status), `TODO.md` (open backlog), and
`scenarios/` (planted signals).

_As of 2026-07-02._

| Collection | Tables | Realism status | Scenarios | Field-enrichment backlog |
|---|---|---|---|---|
| [`hotel`](hotel) | 8 | ✅ Converged | 14 (richest) | ✅ Fully done |
| [`streaming`](streaming) | 8 | ✅ Converged | 8 | 13 of 14 done (`subscriptions.mrr` deferred) |
| [`labor`](labor) | 7 | ✅ Converged (reference collection) | 4 | ✅ Fully done (20 cols) |
| [`clinic`](clinic) | 6 | ✅ Converged | 10 | ⬜ Surveyed, nothing built yet |
| [`insurance`](insurance) | 8 | ✅ Converged (2 fixes landed) | 3 | 🔨 9 quick-win cols + 3 tables built (`adjusters`, `quotes`, `premium_billing`); high-leverage items surveyed |
| [`logistics`](logistics) | 5 | ✅ Converged | 3 | ⬜ Surveyed, nothing built yet |
| [`retail`](retail) | 5 | ⚠️ **Needs investigation** | 3 | ⬜ Surveyed, nothing built yet |

**Totals:** 7 collections, 47 tables.

## Notes

- **retail** is the only collection not converged on realism: invariants and the
  planted category signals are solid, but no dedicated too-synthetic sweep has run
  yet, so several dimensions are likely too clean.
- **hotel / streaming / labor** are the mature trio — realism converged *and* the
  field-enrichment backlog essentially complete. hotel is the flagship (14 scenarios,
  full ADR/RevPAR revenue split); labor is the worked reference collection.
- **clinic / logistics / retail** are converged (or near) on realism but their
  enrichment backlogs are surveyed only — candidate columns are written up in each
  `TODO.md`, none implemented yet. **insurance** is furthest into its backlog: it
  cleared all 9 quick-win columns and built three signal-free tables (`adjusters`,
  `quotes`, `premium_billing`), leaving only the scenario-bearing high-leverage items
  surveyed.
- Every collection ships a full doc set (`realism-guidance.md` / `realism-log.md` /
  `TODO.md`), an invariant `test_*.py` suite, and a `test_scenarios.py`.
