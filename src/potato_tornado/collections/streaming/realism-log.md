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

## Field-enrichment runs

- **2026-07-01 — Field-enrichment survey + build (13 of 14 shipped; `subscriptions.mrr`
  deferred → [`TODO.md`](TODO.md)).** 8 quick wins + 5 high-leverage (scenario-bearing) columns
  across `plans` (`max_streams`, `video_quality`, `ad_supported`), `regions` (`currency`),
  `titles` (`runtime_minutes`, `maturity_rating`, `avg_rating`), `subscribers`
  (`device_platform`, `acquisition_channel`), `subscriptions` (`billing_cycle`,
  `cancel_reason`), and `rentals` (`payment_method`, `rating`). Each reconciled
  `realism-guidance.md` + tests; five planted scenario docs. Full record in
  [`TODO.md`](TODO.md). (`8ffba28`, `13793d9`)
