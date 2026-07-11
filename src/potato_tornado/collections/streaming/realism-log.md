# Realism log — streaming

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — subscriptions + PVOD rentals with regional licensing are in place, and
a rental-price-skew realism fix has landed; residual items are documented candidates, mostly
future scenarios (open items in `TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Build + realism docs.** Plan ladder, regional catalogue licensing (a
  subscriber only rents titles licensed in their region), and the parody title/genre pairing,
  with a realism rubric. (`b2eeb4e`)
- **2026-07-01 — Realism fix: rental-price skew.** Reworked the PVOD rental price so it is
  right-skewed rather than flat, and added invariant tests. (`8ffba28`)
- **2026-07-11 — Realism fix: subscription right-censoring.** Right-censored the subscription
  lifecycle at the window end. A cancelled subscription whose derived churn date
  (`signup_date + tenure×30d`) lands on/after `ctx.config.end_date` now reads `active` with a
  null `end_date` (its churn is in the unobservable future) rather than spilling past the
  window — so a cancelled `end_date` always settles strictly inside the window. Pure
  re-derivation off the existing `is_cancelled` / `tenure` draws — no new RNG, no reordering —
  so `mrr` and every other column stayed byte-identical; only the spilled rows flipped (29/1000
  at seed=7/scale=0.5, 15/600 at scale=0.3). Re-measured + reconciled magnitudes: observed
  cancelled share 0.214 → 0.185, cancelled-monthly tenure mean 5.6 → 5.3, channel churn ladder
  ≈0.08 (organic) … ≈0.34 (paid_search), monthly ≈0.21 vs annual ≈0.06, cancel-reason segment
  shares (content ≈0.40 narrow / ≈0.16 rest; price ≈0.46 Basic / ≈0.29 other) — updated
  `realism-guidance.md` (deleted the "settle after the window" simplification) and the three
  churn scenarios. Added `test_cancelled_subscriptions_settle_within_the_window`; all scenario
  orderings still hold. Cross-collection convention change: `labor` right-censors project
  completions in the same pass, while `hotel` deliberately retains the check-out-spill
  convention (its stays are completed-revenue records) — a documented exception.

## Field-enrichment runs

- **2026-07-01 — Field-enrichment survey + build (13 of 14 shipped; `subscriptions.mrr`
  deferred → [`TODO.md`](TODO.md)).** 8 quick wins + 5 high-leverage (scenario-bearing) columns
  across `plans` (`max_streams`, `video_quality`, `ad_supported`), `regions` (`currency`),
  `titles` (`runtime_minutes`, `maturity_rating`, `avg_rating`), `subscribers`
  (`device_platform`, `acquisition_channel`), `subscriptions` (`billing_cycle`,
  `cancel_reason`), and `rentals` (`payment_method`, `rating`). Each reconciled
  `realism-guidance.md` + tests; five planted scenario docs. Full record in
  [`TODO.md`](TODO.md). (`8ffba28`, `13793d9`)
- **2026-07-11 — `subscriptions.mrr` (14 of 14; enrichment backlog complete).** Materialized the
  deferred MRR convenience column as a pure derivation (no RNG): `plans.monthly_price` for monthly
  subscriptions, `round(monthly_price × ANNUAL_MRR_FACTOR, 2)` with `ANNUAL_MRR_FACTOR = 10/12`
  ("2 months free") for annual. Added the MRR-identity invariant to `realism-guidance.md` and a
  single-assert invariant test. No random draws introduced, so all existing columns remained
  byte-identical at seed=7/scale=0.3.
