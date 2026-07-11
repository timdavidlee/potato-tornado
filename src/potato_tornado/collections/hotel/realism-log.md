# Realism log — hotel

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — the most scenario-rich collection (14 scenarios); realism docs and
audits are in place, and residual items are documented candidates to *promote into scenarios*,
not realism defects (open items in `TODO.md`). Re-affirmed 2026-07-11 after closing the last two
non-scenario realism candidates (forecast error band investigated → infeasible; check-out
right-censoring deferred as a documented exception), both as deliberate simplifications with no
generator change. (as of 2026-07-11)

## Realism iterations

- **2026-07-01 — Realism docs + enrichment build.** Room upgrades, stay changes, service book,
  and demand forecast added with realism guidance covering the rate ladder, lead time, and
  forecast-vs-realised occupancy. (`b2eeb4e`)
- **2026-07-01 — Realism audit + invariant tests.** Verified reservation→stay linkage,
  arithmetic identities (revenue = rate × nights), and the rate/occupancy mixes. (`8ffba28`)
- **2026-07-11 — Nightly-rate calendar de-lattice.** `stays.nightly_rate` had been a flat
  lattice (one value per (property, room_class)); replaced it with a per-stay **billed** rate =
  rack × day-of-year summer season (`_RATE_SEASON_AMP` 0.15, peak mid-July at `_RATE_PEAK_DOY`
  196, matching `reservations._PEAK_DOY`) × Fri–Sun weekend lift (`_RATE_WEEKEND_LIFT` 1.10) — a
  pure deterministic derivation, so no other column's draws shift. `room_revenue` / `taxes_fees`
  recompute off it; `taxes_fees` moved to polars-side `.round(2)` so the generator and its
  reconciliation test share one rounding path (room_revenue now carries cents). Dropped the "flat
  rates" deliberate simplification, added the *Rate seasonality & weekend lift* distribution line,
  pinned by `test_nightly_rate_varies_across_the_calendar`. De-latticed as realism (expected), no
  scenario doc.
- **2026-07-11 — Two realism candidates investigated and closed (docs-only, no generator change).**
  (1) *Forecast error band covary with demand* — **infeasible, kept as a deliberate
  simplification.** Occupancy is a near-uniform ≈8% everywhere, so an `occ_frac`-scaled `sd`
  can't create a low-vs-high-occupancy APE differential, and integer rounding of
  `forecast_occupied_rooms` already damps low-occupancy APE the opposite way; no
  demand-sensitivity coefficient flips low-occ APE above high-occ APE while keeping the pinned
  `test_forecast_tracks_actual_within_about_ten_percent` green (would need `sd` ≈0.3+, tripling
  MAPE past its 0.16 ceiling). The flat weekday/weekend band (`sd` 0.09/0.22) stays deliberate;
  extended the forecast bullet in `realism-guidance.md` and corrected a stale `Normal(1, 0.12)`
  comment on the pinned test (the code uses 0.09/0.22). (2) *Right-censoring of check-outs past
  the window* — **deferred as a documented exception.** `hotel` deliberately retains the
  check-out-spill-past-window convention because `stays` are completed-revenue records (unlike
  `labor` projects / `streaming` subscriptions, which carry an active-status flag + nullable end
  and are being right-censored); the faithful revenue-recompute version breaks the drift/revenue
  invariants and the minimal version adds a second nullable column for no analytical gain. Added
  the exception to `realism-guidance.md` deliberate simplifications. Both items ticked in
  `TODO.md` + the dated checklist. No `tables/*.py` changed.

## Field-enrichment runs

- **2026-07-01 — Field-enrichment survey + full build (backlog complete).** 10 quick wins (new
  dimensions to slice by, e.g. `reservations.market_segment`) + 4 high-leverage items + the
  ADR / RevPAR revenue split (`stays.taxes_fees` as a pure tax-wedge derivation, plus
  `room_count`), so ADR / RevPAR / TRevPAR are all computable. Five items planted scenario docs
  (incl. the Iberia tax-load signal). Each reconciled `realism-guidance.md` + tests. Full record
  in [`TODO.md`](TODO.md). (`b2eeb4e`, `13793d9`)
