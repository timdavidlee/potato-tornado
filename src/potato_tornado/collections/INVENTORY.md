# Collections inventory

A snapshot of the built-in data collections: table count, realism status, scenario
coverage, and field-enrichment backlog state. Per-collection detail lives in each
package's `realism-log.md` (history + status), `TODO.md` (open backlog), and
`scenarios/` (planted signals).

_As of 2026-07-11._

| Collection | Tables | Realism status | Scenarios | Field-enrichment backlog |
|---|---|---|---|---|
| [`hotel`](hotel) | 8 | ✅ Converged | 14 (richest) | ✅ Fully done (calendar rate-variation realized; forecast-band investigated → infeasible; star/YoY scenario candidate open) |
| [`streaming`](streaming) | 8 | ✅ Converged | 8 | ✅ Fully done (14 of 14 + subscription right-censoring) |
| [`labor`](labor) | 12 | ✅ Converged (reference collection) | 4 | ✅ Round-1 (20 cols) + round-2 (6 cols + 5 tables) + project right-censoring; `assignments.assigned_at` signal → scenario |
| [`retail`](retail) | 6 | ✅ Converged | 3 | ✅ Economics done: `discount_pct` + flat `cost`/`promo` + `order_charges` (shipping/tax); margin/promo signals → scenario |
| [`insurance`](insurance) | 10 | ✅ Converged | 3 | ✅ High-leverage cols (flat) + `claim_status_history` + `coverage_lines`; `reinsurance` → new collection; signals → scenario |
| [`clinic`](clinic) | 6 | ✅ Converged | 10 | 🔨 11 enrichment cols built (7 realism + 4 flat scenario-cols); scenario signals open |
| [`logistics`](logistics) | 5 | ✅ Converged | 3 | 🔨 7 quick wins + 2 high-leverage + hub-city de-lattice; 3 scenario-bearing cols routed |

**Totals:** 7 collections, 55 tables.

## Notes

- **All 7 collections remain converged on realism.** Two field-enrichment + realism
  passes landed on 2026-07-11: pass 1 added flat enrichment columns and de-lattices
  across every collection; pass 2 added two new tables (`retail.order_charges`,
  `insurance.coverage_lines`), applied lifecycle **right-censoring** to `labor` project
  completions and `streaming` subscriptions, and closed hotel's remaining candidates. The
  full repo-wide gate is green (424 tests).
- **hotel / streaming / labor / retail** are the mature group — realism converged *and*
  the field-enrichment backlog complete. hotel is the flagship (14 scenarios); its
  forecast-band item was investigated and closed as infeasible (a documented deliberate
  simplification), leaving only the star/YoY scenario candidate. streaming (14 of 14) and
  labor (round-1 + round-2, the worked reference) both now right-censor derived end-dates
  at the window. retail's checkout economics are complete via the new order-grain
  `order_charges` table (merchandise + shipping + tax).
- **Right-censoring is a deliberate cross-collection choice, not universal:** `labor` and
  `streaming` right-censor lifecycle end-dates at the window, while `hotel` intentionally
  retains the check-out-spill convention because its `stays` are completed-revenue records
  — documented as an exception in each collection's `realism-guidance.md`.
- **insurance** is converged with its in-collection enrichment complete — the high-leverage
  columns (flat), the `claim_status_history` lifecycle table, and the `coverage_lines`
  premium-side breakdown all shipped; a `reinsurance` domain is deferred to
  `/data-collection:propose` as its own collection, and the planted signals route to
  `/scenario:draft-or-propose`.
- **clinic / logistics** have substantially built backlogs with scenario-bearing work
  routed out: clinic shipped 11 enrichment columns (7 realism + 4 flat scenario-columns,
  signals open); logistics de-latticed the multi-hop hub city and routed its 3
  scenario-bearing columns.
- Every collection ships a full doc set (`realism-guidance.md` / `realism-log.md` /
  `TODO.md`), an invariant `test_*.py` suite, and a `test_scenarios.py`.
