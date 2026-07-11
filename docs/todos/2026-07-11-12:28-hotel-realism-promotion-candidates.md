# Hotel realism / scenario-promotion candidates — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `hotel` collection only.
- **Source:** [`collections/hotel/TODO.md`](../../src/potato_tornado/collections/hotel/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/hotel/realism-log.md)).
- **Status:** the field-enrichment backlog is **fully done** (10 quick wins + 4 high-leverage +
  the ADR/RevPAR revenue split, five with scenario docs). The only open work is the three
  **open realism items** below — all documented candidates to *promote into scenarios*, not
  realism defects. Nearly-done collection; this list is short by design.

## How to work this list

These are not new columns — they are existing dimensions that read flat and are candidates to
turn into a planted signal:

- Investigate with `/data-collection:review-edit-regen-for-realism hotel` first (measure the
  cross-tab, decide whether it's a drift to fix or an intentional flat).
- Where the interesting part is a **surprising slice**, promote it via
  `/scenario:draft-or-propose hotel` then `/scenario:review-and-edit-regenerate`.

**Definition of done** (if a change lands): draw only from `ctx.dist` / `ctx.rng.child` /
`ctx.entities` on a **name-keyed child stream** without reordering existing draws; reconcile the
matching line in `realism-guidance.md`; add/extend a test in
`tests/collections/hotel/test_hotel.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## Open realism items to investigate

- [ ] **No weekday/weekend or seasonal rate variation.** Rates are flat by calendar (a documented
  simplification); a rate-by-day-of-week series reads implausibly flat — the strongest
  realism-flavoured candidate.
  - Class: **realism** (flat → seasonal) — likely a `/data-collection:review-edit-regen-for-realism`
    fix, or promote a season/weekend rate lift as a scenario.

- [ ] **Forecast error band is flat across segments.** Documented as not varying by weekend; a
  candidate to make forecast error covary with demand.
  - Class: **realism** — make the error band demand-dependent.

- [ ] **Star-rating review premium / YoY demand trend not wired.** Both are documented candidates
  to promote into scenarios; today the cross-tabs read flat.
  - Class: **scenario-bearing** → `/scenario:draft-or-propose hotel` (e.g. *higher-star properties
    earn a review premium*, or *a year-over-year demand trend*).

## When the list is done

Nothing further is queued for hotel — the enrichment backlog is complete and reconciled. If all
three items above are resolved (fixed or deliberately closed), hotel has no open work.

---

## Suggested order

1. **Weekday/weekend + seasonal rate variation** — the most visible flat artifact; biggest
   realism payoff and a natural rate-by-day scenario.
2. **Forecast error band by demand** — smaller realism refinement.
3. **Star-rating premium / YoY trend** — pure scenario-promotion; route to
   `/scenario:draft-or-propose hotel`.
