# Logistics scenario-bearing columns + realism items — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `logistics` collection only.
- **Source:** [`collections/logistics/TODO.md`](../../src/potato_tornado/collections/logistics/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/logistics/realism-log.md)).
- **Status:** all **7 quick wins** shipped (2026-07-02) and the two realism high-leverage items
  (`scan_events.facility_type`, parcel dimensions) shipped. Open: the **3 scenario-bearing
  high-leverage columns** and **4 open realism items**.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism logistics`
  (build flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset signal*
  goes through `/scenario:draft-or-propose logistics` then `/scenario:review-and-edit-regenerate`.
  Don't plant the signal during the realism pass.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` / `ctx.entities`
on a **name-keyed child stream** without reordering existing draws; reconcile the matching line in
`realism-guidance.md`; add/extend an invariant test in
`tests/collections/logistics/test_logistics.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## High-leverage columns (scenario-bearing)

- [ ] **`shipments.insured_value`** (`Float64`)
  - File: `tables/shipments.py`. Draw: right-skew via `ctx.dist.lognormal`, floored near the cost;
    own child stream.
  - Unlocks: loss/exposure analysis — value at risk on `lost` / `returned_to_sender` parcels.
  - Class: **scenario-bearing** → *loss rate rises with declared value*, or value concentrates in a
    service tier. Name the subset signal; don't plant it in the realism pass.

- [ ] **`scan_events.exception_reason`** (`Utf8`, nullable — `exception` scans only)
  - File: `tables/scan_events.py`. Draw: `{address_issue, refused, damaged, customs_hold,
    lost_in_transit}` on `exception` scans; null on all happy-path scans; own child stream.
  - Unlocks: a failure-cause funnel behind `returned_to_sender` / `lost` — *why* parcels don't
    arrive, not just that they don't.
  - Class: **scenario-bearing** → *the reason mix differs by `dest_zone` or `carrier`* (far zones
    skew address/customs, cheap carriers skew damage).

- [ ] **`deliveries.delivery_cost`** (`Float64`) — cost vs. price
  - File: `tables/deliveries.py`. Draw: `shipping_cost × margin_factor` with per-service jitter,
    below the customer-facing `shipping_cost`; own child stream.
  - Unlocks: unit-economics — gross margin per shipment, margin by lane/service.
  - Class: **scenario-bearing** → *margin is thin or negative on far zones / overnight*.

## Open realism items to investigate

Route to `/data-collection:review-edit-regen-for-realism logistics` (existing data, not new
fields).

- [ ] **Intermediate `in_transit` hub city is drawn once per shipment** and repeats across a
  multi-hop parcel, unrelated to origin→destination geography. Check whether hub cities should
  vary per hop and sit "between" origin and destination.
- [ ] **`dest_zone` is independent of `dest_city` / `warehouses.city`.** A distance proxy with no
  geographic grounding — measure whether a zone × city cross-tab looks implausible.
- [ ] **Memoryless outcomes.** On-time, terminal status, and early/late days are independent per
  shipment — no per-carrier streaks, seasonality, or weather. Confirm no autocorrelation is
  expected.
- [ ] **Cost-tail sanity.** Re-confirm the cost tail past \$80 is weight-driven and not clipping
  oddly at the `weight_kg` clamp (50 kg) — spot-check the top decile.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** Reconcile the rubric and invariant tests with the new
  columns (e.g. `exception_reason` non-null iff terminal scan is `exception`,
  `delivery_cost < shipping_cost`).

_Out of scope: a recipient / customer dimension is a new entity, not a column → `/data-collection:propose`._

---

## Suggested order

1. **`deliveries.delivery_cost`** — unlocks unit-economics (margin), the highest-leverage single
   column; build flat, then route the thin-margin subset to `/scenario:draft-or-propose logistics`.
2. **`scan_events.exception_reason`** — the failure-cause funnel; pairs with the existing
   returned/lost outcomes.
3. **`shipments.insured_value`** — value-at-risk exposure.
4. **Open realism items** — the hub-city / `dest_zone` geography pair is the most visible synthetic
   tell; sweep them in one `/data-collection:review-edit-regen-for-realism logistics` pass.
