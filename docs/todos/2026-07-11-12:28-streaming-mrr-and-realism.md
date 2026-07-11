# Streaming deferred column + realism items — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `streaming` collection only.
- **Source:** [`collections/streaming/TODO.md`](../../src/potato_tornado/collections/streaming/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/streaming/realism-log.md)).
- **Status:** **13 of 14** enrichment items shipped (all 8 quick wins + all 5 high-leverage, five
  with scenario docs). Open: the **one deferred convenience column** (`subscriptions.mrr`, "hold
  unless asked") and **4 open realism items**. Nearly-done collection.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism streaming`
  (build flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset signal*
  goes through `/scenario:draft-or-propose streaming` then `/scenario:review-and-edit-regenerate`.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` / `ctx.entities`
on a **name-keyed child stream** without reordering existing draws; reconcile the matching line in
`realism-guidance.md`; add/extend an invariant test in
`tests/collections/streaming/test_streaming.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## Deferred column

- [ ] **`subscriptions.mrr`** (`Float64`) — derived convenience column *(deferred: "hold unless asked")*
  - File: `tables/subscriptions.py`. Draw: **pure derivation, no RNG** — `plans.monthly_price`, or
    the annual-discounted monthly equivalent when `billing_cycle = 'annual'`. `subscriptions`
    already `depends_on ("plans")`.
  - Unlocks: MRR pre-computed rather than joined — low value unless a lesson wants it materialized.
  - Class: **realism** (derivation). Only build if a lesson actually needs it.

## Open realism items to investigate

Route to `/data-collection:review-edit-regen-for-realism streaming` (existing data, not new fields).

- [ ] **No heavy-renter concentration.** Rentals spread ~uniformly across subscribers
  (rentals/subscriber ≈ Poisson) — no whale minority driving PVOD revenue. The strongest
  realism-flavoured candidate (documented as a future scenario). Class: **scenario-bearing**.
- [ ] **Subscription lifecycle is birth-only.** Rows capture the signup window but not
  right-censoring / churn dynamics after it — a candidate future invariant. Class: **realism**.
- [ ] **`is_premium` is release-date independent.** Newer releases aren't tilted toward the premium
  tier the way real PVOD is; the premium-by-release-year cross-tab reads flat. Class:
  **scenario-bearing**.
- [ ] **Device/region mixes are flat, unplanted.** No device-mix-by-region or maturity-by-genre
  skew — realism dimensions to slice by, currently uniform. Class: **realism** (→ scenario if a
  slice is planted).

## When the list is done

`realism-guidance.md` was already reconciled during the enrichment build. If the four realism items
are resolved (fixed or deliberately closed) and `mrr` is either built or explicitly declined,
streaming has no open work.

---

## Suggested order

1. **Open realism items first** — `streaming`'s enrichment is complete, so the value now is in the
   realism sweep. Lead with **heavy-renter concentration** (the strongest tell, a natural PVOD-whale
   scenario) and **`is_premium` by release-date**; both are scenario-bearing.
2. **Device/region mix + subscription lifecycle** — realism dimensions; sweep in the same pass.
3. **`subscriptions.mrr`** — only if a lesson asks for a materialized MRR; otherwise leave deferred.
