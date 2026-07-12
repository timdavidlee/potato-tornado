# Collections inventory

A snapshot of the built-in data collections: table count, realism status, scenario
coverage, and field-enrichment backlog state. Per-collection detail lives in each
package's `realism-log.md` (history + status), `TODO.md` (open backlog), and
`scenarios/` (planted signals).

_As of 2026-07-11._

| Collection | Tables | Realism status | Scenarios | Field-enrichment backlog |
|---|---|---|---|---|
| [`hotel`](hotel) | 8 | ✅ Converged | 16 (richest) | ✅ Fully done (calendar rate-variation realized; forecast-band investigated → infeasible; star/YoY scenario candidate still open) |
| [`streaming`](streaming) | 8 | ✅ Converged | 10 | ✅ Fully done (14 of 14 + subscription right-censoring) |
| [`labor`](labor) | 12 | ✅ Converged (reference collection) | 6 | ✅ Round-1 (20 cols) + round-2 (6 cols + 5 tables) + project right-censoring; `assignments.assigned_at` signal → realized (short-notice no-show) |
| [`retail`](retail) | 6 | ✅ Converged | 5 | ✅ Economics done: `discount_pct` + `cost`/`promo` + `order_charges` (shipping/tax); margin signal → realized (promo signal still open) |
| [`insurance`](insurance) | 10 | ✅ Converged | 5 | ✅ High-leverage cols + `claim_status_history` + `coverage_lines`; `reinsurance` → new collection; litigation signal → realized |
| [`clinic`](clinic) | 6 | ✅ Converged | 12 | 🔨 11 enrichment cols built (7 realism + 4 flat scenario-cols); reminder + payer-adjudication signals → realized |
| [`logistics`](logistics) | 5 | ✅ Converged | 5 | 🔨 7 quick wins + 2 high-leverage + hub-city de-lattice; 2 of 3 scenario-bearing cols realized (dim-weight, signature) |

**Totals:** 7 collections, 55 tables, 59 scenarios.

## Notes

- **Scenario round (2026-07-11).** Drafted 14 new scenario docs (one–two per collection),
  then realized all 14 as scenario tests over two PRs: **8 already-produced signals**
  (hotel over-capacity + RevPAR inversions, logistics dim-weight + signature gradient,
  insurance exposure-vs-frequency, streaming US-ARPU + annual-MRR, retail shipping
  regressivity) shipped test-only in v0.3.0; **6 planted signals** (clinic reminder→no-show
  + payer adjudication, labor short-notice no-show + billing-type realization, retail
  category margin, insurance litigation tax) tuned the `tables/` generators to plant the
  signal while holding each collection's marginals. Full repo-wide gate green (438 tests).
- **All 7 collections remain converged on realism.** The earlier two field-enrichment +
  realism passes (also 2026-07-11) added flat enrichment columns and de-lattices across
  every collection, two new tables (`retail.order_charges`, `insurance.coverage_lines`),
  and lifecycle **right-censoring** to `labor` project completions and `streaming`
  subscriptions.
- **hotel / streaming / labor / retail** are the mature group — realism converged *and*
  the field-enrichment backlog complete. hotel is the flagship (16 scenarios); its
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
  columns, the `claim_status_history` lifecycle table, and the `coverage_lines`
  premium-side breakdown all shipped; a `reinsurance` domain is deferred to
  `/data-collection:propose` as its own collection.
- **clinic / logistics** have substantially built backlogs with scenario-bearing work now
  largely realized: clinic shipped 11 enrichment columns (7 realism + 4 flat
  scenario-columns) and realized the reminder + payer-adjudication signals; logistics
  de-latticed the multi-hop hub city and realized 2 of its 3 scenario-bearing columns.
- Every collection ships a full doc set (`realism-guidance.md` / `realism-log.md` /
  `TODO.md`), an invariant `test_*.py` suite, and a `test_scenarios.py`.
