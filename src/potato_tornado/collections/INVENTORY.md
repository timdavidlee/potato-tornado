# Collections inventory

A snapshot of the built-in data collections: table count, realism status, scenario
coverage, and field-enrichment backlog state. Per-collection detail lives in each
package's `realism-log.md` (history + status), `TODO.md` (open backlog), and
`scenarios/` (planted signals).

_As of 2026-07-11._

| Collection | Tables | Realism status | Scenarios | Field-enrichment backlog |
|---|---|---|---|---|
| [`hotel`](hotel) | 8 | ✅ Converged | 14 (richest) | ✅ Fully done (3 realism→scenario promotion candidates open) |
| [`streaming`](streaming) | 8 | ✅ Converged | 8 | 13 of 14 done (`subscriptions.mrr` deferred) |
| [`labor`](labor) | 7 | ✅ Converged (reference collection) | 4 | ✅ Round-1 done (20 cols); round-2 surveyed (7 cols + 5 tables) |
| [`insurance`](insurance) | 8 | ✅ Converged | 3 | 🔨 9 quick-win cols + 3 tables built (`adjusters`, `quotes`, `premium_billing`); 7 high-leverage cols + 3 tables open |
| [`logistics`](logistics) | 5 | ✅ Converged | 3 | 🔨 7 quick wins + 2 high-leverage built; 3 scenario-bearing cols open |
| [`retail`](retail) | 5 | ✅ Converged (sweep landed) | 3 | 🔨 6 quick wins + `returns.item_condition` built; 4 economics cols open |
| [`clinic`](clinic) | 6 | ✅ Converged | 10 | ⬜ Surveyed, nothing built yet |

**Totals:** 7 collections, 47 tables.

## Notes

- **All 7 collections are now converged on realism.** retail's first dedicated
  too-synthetic sweep landed (2026-07-02) — the product-name lattice and missing
  seasonality were fixed, the rest judged deliberate — clearing the last
  "needs investigation" outlier.
- **hotel / streaming / labor** are the mature trio — realism converged *and* the
  field-enrichment backlog essentially complete. hotel is the flagship (14 scenarios,
  full ADR/RevPAR revenue split; only 3 realism→scenario promotion candidates left);
  labor is the worked reference (round-1's 20 columns done, a round-2 backlog freshly
  surveyed). streaming has one deferred convenience column (`subscriptions.mrr`).
- **insurance / logistics / retail** have partially built backlogs. **insurance** is
  furthest: all 9 quick-win columns plus three signal-free tables (`adjusters`,
  `quotes`, `premium_billing`), leaving the scenario-bearing high-leverage columns and
  three simplification-tension tables open. **logistics** (7 quick wins + 2
  high-leverage) and **retail** (6 quick wins + `returns.item_condition`) each shipped
  their quick wins, with scenario-bearing columns still open.
- **clinic** is converged with a rich scenario set (10) but its enrichment backlog is
  surveyed only — candidate columns are written up in `TODO.md`, none implemented yet.
- Every collection ships a full doc set (`realism-guidance.md` / `realism-log.md` /
  `TODO.md`), an invariant `test_*.py` suite, and a `test_scenarios.py`.
