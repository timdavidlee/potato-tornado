# Hotel — dated working checklist (2026-07-11 12:28)

- **Scope:** the `hotel` collection only.
- **Source of truth:** [`collections/hotel/TODO.md`](../../src/potato_tornado/collections/hotel/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/hotel/realism-log.md). Workflow lives in
  [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** field-enrichment backlog fully done; only these promotion/realism candidates were
  open. Calendar rate-variation realized 2026-07-11; the forecast error band was investigated
  the same day and closed as infeasible (kept as a deliberate simplification, no generator
  change); only the scenario-bearing star-rating / YoY item remains.

## Checklist

**Open realism items →** [`TODO.md` § Open realism items to investigate](../../src/potato_tornado/collections/hotel/TODO.md#open-realism-items-to-investigate)

- [x] No weekday/weekend or seasonal rate variation *(2026-07-11 — de-latticed)*
- [x] Forecast error band is flat across segments *(2026-07-11 — investigated → infeasible; kept as deliberate simplification. Demand-covariance is un-pinnable: ≈8% uniform occupancy gives no low-vs-high differential, integer rounding damps low-occ APE the opposite way, and no `sd` satisfies both the demand signal and the pinned MAPE test. No generator change; documented in realism-guidance.)*
- [ ] Star-rating review premium / YoY demand trend not wired
