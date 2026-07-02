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
not realism defects (open items in `TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Realism docs + enrichment build.** Room upgrades, stay changes, service book,
  and demand forecast added with realism guidance covering the rate ladder, lead time, and
  forecast-vs-realised occupancy. (`b2eeb4e`)
- **2026-07-01 — Realism audit + invariant tests.** Verified reservation→stay linkage,
  arithmetic identities (revenue = rate × nights), and the rate/occupancy mixes. (`8ffba28`)

## Field-enrichment runs

- **2026-07-01 — Field-enrichment survey + full build (backlog complete).** 10 quick wins (new
  dimensions to slice by, e.g. `reservations.market_segment`) + 4 high-leverage items + the
  ADR / RevPAR revenue split (`stays.taxes_fees` as a pure tax-wedge derivation, plus
  `room_count`), so ADR / RevPAR / TRevPAR are all computable. Five items planted scenario docs
  (incl. the Iberia tax-load signal). Each reconciled `realism-guidance.md` + tests. Full record
  in [`TODO.md`](TODO.md). (`b2eeb4e`, `13793d9`)
