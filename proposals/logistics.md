# logistics — collection proposal

- **Domain:** parcels dispatched from fulfillment warehouses through a carrier
  network, tracked by a stream of scan events, and measured against a promised
  delivery date (the SLA).
- **Teaching value:** the first collection with a **per-entity event log** — each
  shipment emits several ordered tracking scans, so students learn to reconstruct a
  timeline from many rows per parent (window functions, first/last scan, elapsed
  time between events). The existing four all terminate in a single 1:1
  "reality" row; none teach a variable-length event stream. It also carries a
  **promised-vs-actual SLA** whose miss rate rises with shipping distance (zone) —
  a covariate-driven degradation distinct from clinic's lead-time gradient.

## Tables

Build order (a DAG): `carriers`, `warehouses` → `shipments` → `scan_events` →
`deliveries`.

- `carriers` — the carrier catalog (dim). Seeded from `constants.CARRIERS`.
  Columns: `carrier_id: Utf8` (`CAR-01`), `carrier_name: Utf8`,
  `base_rate: Float64` (per-shipment base cost), `per_kg_rate: Float64`,
  `reliability: Float64` (on-time propensity, ≈0.85–0.97). `depends_on=()`.

- `warehouses` — origin fulfillment centers (dim). Columns:
  `warehouse_id: Utf8` (`WH-001`), `city: Utf8` (from `ctx.entities.cities`),
  `region: Utf8` (one of a few coarse regions). `depends_on=()`.

- `shipments` — the core fact, one row per parcel dispatched. Holds the **plan**
  (`promised_date`). Columns: `shipment_id: Utf8` (`SHP-0000001`),
  `warehouse_id: Utf8 → warehouses.warehouse_id`,
  `carrier_id: Utf8 → carriers.carrier_id`,
  `service_level: Utf8` (`ground`/`express`/`overnight`),
  `dest_city: Utf8` (from `ctx.entities.cities`),
  `dest_zone: Int64` (1–8, distance proxy),
  `weight_kg: Float64` (right-skew),
  `shipping_cost: Float64` (right-skew, weight- and zone-driven),
  `ship_date: Date` (spread across the full window),
  `promised_date: Date` (`ship_date` + promised transit days for the service level).
  `depends_on=("warehouses", "carriers")`.

- `scan_events` — the tracking event log: **several ordered rows per shipment**
  forming its journey. Columns: `scan_id: Utf8` (`SCN-00000001`),
  `shipment_id: Utf8 → shipments.shipment_id`,
  `seq: Int64` (1..k, order within the shipment),
  `scan_type: Utf8` (from the `SCAN_TYPES` ladder:
  `picked_up`/`in_transit`/`out_for_delivery`/`delivered`/`exception`),
  `scan_ts: Datetime`, `location_city: Utf8`.
  `depends_on=("shipments",)`.

- `deliveries` — the terminal outcome (the **actual**), 1:1 with `shipments`,
  derived from each shipment's terminal scan. Columns: `delivery_id: Utf8`
  (`DLV-0000001`), `shipment_id: Utf8 → shipments.shipment_id`,
  `status: Utf8` (`delivered`/`returned_to_sender`/`lost`),
  `actual_delivery_date: Date | null` (null unless `delivered`),
  `days_late: Int64 | null` (`actual_delivery_date − promised_date`, signed;
  null unless `delivered`), `attempts: Int64` (1–3).
  `depends_on=("shipments", "scan_events")`.

`deliveries` reads the terminal row of each shipment's `scan_events` timeline so
the two tables never disagree about whether/when a parcel was delivered — hence the
`scan_events` dependency (still a DAG).

## Constants

`constants.py` candidates (each used by two or more tables):

- `CARRIERS` — `(carrier_name, base_rate, per_kg_rate, reliability)` seed rows for
  the `carriers` dim; `reliability` is later read (via the built table) by
  `scan_events`/`deliveries` to set on-time propensity.
- `SERVICE_LEVELS` — `(name, promised_transit_days, price_multiplier, weight)`,
  read by `shipments` (promised date + cost multiplier) and `deliveries` (the late
  tail scales with the promised window).
- `SCAN_TYPES` — the ordered happy-path ladder
  `["picked_up", "in_transit", "out_for_delivery", "delivered"]` plus the terminal
  `"exception"`, shared by `scan_events` (timeline build) and `deliveries` (terminal
  read) and referenced by the realism doc.

Single-table literals (region list, zone bounds) stay inline in their module.

## Distributions & target magnitudes

All numbers below are **targets to plant**, to be firmed up after the first
generation — not measured values.

- **Row counts (`scale=1.0`):** `carriers` ≈ 5, `warehouses` ≈ 12,
  `shipments` = `ctx.n(8000)`, `scan_events` ≈ 3–6 × shipments (variable),
  `deliveries` = 1:1 with shipments.
- **weight_kg:** `ctx.dist.lognormal(median≈2.0, sigma≈0.8)`, clamped to
  `[0.1, 50]` — most parcels light, a long heavy tail.
- **dest_zone:** integers 1–8, weighted toward the middle zones (distance proxy).
- **shipping_cost (right-skew, arithmetic identity):**
  `round((base_rate + weight_kg × per_kg_rate + dest_zone × zone_fee) ×
  price_multiplier, 2)` → target median ≈ \$9, p95 ≈ \$45, tail past \$80. Skew
  comes from `weight_kg`, not a second lognormal draw.
- **ship_date:** `ctx.dist.dates_between(start_date, end_date)` — uniform across the
  full ~3-year window (no clustering).
- **service mix:** ground 0.70 / express 0.22 / overnight 0.08; promised transit
  ground 5d, express 2d, overnight 1d.
- **scan count:** 4 on the happy path (`picked_up → in_transit →
  out_for_delivery → delivered`), +1 `in_transit` hop for higher zones, +1
  `exception` for non-delivered — so ≈3–6 rows/shipment.
- **on-time rate:** overall ≈88% delivered on or before `promised_date`; the late
  tail (`days_late > 0`) is right-skewed, mean ≈ +2–3 days, up to ≈ +7. On-time
  propensity blends carrier `reliability`, service level, and zone (see scenario 1).
- **terminal status mix:** delivered 0.965 / returned_to_sender 0.025 / lost 0.010;
  non-delivered rows carry null `actual_delivery_date` and null `days_late`.
- **attempts:** 1 (0.82) / 2 (0.14) / 3 (0.04), skewing higher for late/returned.

## Candidate scenarios

- **On-time delivery degrades with shipping zone.** Signal: the farther the
  destination zone, the lower the on-time rate. Tables: `shipments.dest_zone`,
  `shipments.promised_date`, `deliveries.days_late`. Target: on-time
  (`days_late ≤ 0`) falls from ≈95% at zone 1 to ≈78% at zone 8 (~1.2× the miss
  rate per few zones). How to find it: `select dest_zone,
  avg((days_late <= 0)::int) from deliveries join shipments using (shipment_id)
  where status='delivered' group by dest_zone order by dest_zone;` → rate declines.

- **Shipping cost is right-skewed and weight-driven.** Signal: a long cost tail;
  heavy parcels dominate spend. Tables: `shipments.shipping_cost`,
  `shipments.weight_kg`. Target: median ≈ \$9, p95 ≈ \$45, max past \$80; cost rises
  ~linearly in weight. How to find it: `select
  quantile(shipping_cost, 0.5), quantile(shipping_cost, 0.95), max(shipping_cost)
  from shipments;` (and `corr(weight_kg, shipping_cost)` ≈ strong positive).

- **Promised-vs-actual SLA and the late tail** (plan-vs-actual). Signal: most
  shipments meet the promised date; a right-skewed minority run late. Tables:
  `shipments.promised_date`, `deliveries.actual_delivery_date`,
  `deliveries.days_late`. Target: ≈88% on-time overall; late tail mean +2–3 days,
  reaching +7. How to find it: `select days_late, count(*) from deliveries where
  status='delivered' group by days_late order by days_late;` → mass at ≤0, thin
  right tail.

(A fourth candidate — the **exception/return funnel** (96.5% delivered / 2.5%
returned / 1% lost, with attempts rising for non-delivered) — is a natural later
scenario once the terminal-status mix is planted.)

## Realism guidance (seed)

**Invariants — must always hold:**
- Referential integrity: `shipments.warehouse_id ∈ warehouses`,
  `shipments.carrier_id ∈ carriers`, `scan_events.shipment_id ∈ shipments`,
  `deliveries.shipment_id ∈ shipments` and `deliveries` is 1:1 with `shipments`.
- Temporal ordering: within a shipment, `scan_events` rows have strictly increasing
  `scan_ts` matching `seq`; the first scan is on/after `ship_date`;
  `promised_date ≥ ship_date`; `actual_delivery_date ≥ ship_date`.
- Terminal consistency: `status='delivered'` ⇔ a `delivered` scan exists ⇔
  `actual_delivery_date` and `days_late` are both non-null; a non-delivered status ⇔
  both are null and the terminal scan is `exception`. No third state.
- Arithmetic identities: `days_late = actual_delivery_date − promised_date` (signed);
  `shipping_cost` equals the cost formula above.
- Non-negativity / bounds: `weight_kg > 0`, `shipping_cost > 0`, `dest_zone ∈ [1,8]`,
  `attempts ∈ [1,3]`, `seq ≥ 1`.

**Deliberate simplifications — intended, do not "fix":**
- One `deliveries` row per shipment: no split shipments or multi-parcel orders.
- Scan `location_city` is a coarse city label (from `ctx.entities.cities`), not a
  facility code or lat/long; intermediate hops are synthetic.
- Transit is measured in calendar days — no weekend/holiday pauses.
- Flat `per_kg_rate`: no dimensional weight, fuel surcharges, or customs.
- `dest_zone` is a per-shipment distance proxy, not computed from warehouse/dest
  geography.

## Building it

Follows the "Adding a collection" checklist in
[collections/CLAUDE.md](../src/potato_tornado/collections/CLAUDE.md):

1. `collections/logistics/` with `__init__.py`, `constants.py`, `tables/`
   (+ `__init__.py`), `scenarios/`, `realism-guidance.md`.
2. One `build_<table>` per table under `tables/`
   (`carriers`, `warehouses`, `shipments`, `scan_events`, `deliveries`);
   re-export from `tables/__init__.py`.
3. Assemble the `Collection` with the `depends_on` wiring above and
   `register("logistics", build)` in `__init__.py`.
4. Add `"potato_tornado.collections.logistics"` to `_BUILTIN_MODULES` in
   [`core/registry.py`](../src/potato_tornado/core/registry.py).
5. Write `scenarios/*.md` for the three signals above.
6. Write `realism-guidance.md` from the seed above.
7. Add a `logistics` row to the README collections table.
8. Mirror tests under `tests/collections/logistics/`; `tests/test_runner.py` picks
   up determinism / non-empty checks automatically.

**Core APIs it leans on (all exist today):** `ctx.dist.lognormal` / `money` /
`integers` / `choice` / `dates_between` / `combine` for weights, cost, zones,
dates, and scan timestamps; `ctx.entities.cities` for warehouse and destination
cities; `ctx.n(base)`, `ctx.config.span_days`, `ctx.table(...)` per usual.

**New helpers needed — none required, one thing to note.** The variable-length
`scan_events` fan-out follows the existing list-extend loop idiom
([`labor/tables/assignments.py`](../src/potato_tornado/collections/labor/tables/assignments.py)).
On-time propensity is a **per-row** probability (it depends on carrier reliability,
service, and zone), but `ctx.dist.bernoulli(n, p)` only takes a scalar `p`. As
`labor` already does, drop to `ctx.rng.numpy` and compare a per-row probability
array directly (`ctx.rng.numpy.random(n) < p_array`) rather than adding a new
vectorized-`p` Bernoulli helper — unless the same pattern is wanted elsewhere, in
which case promote a `dist.bernoulli_p(p_array)` into `core/distributions.py` at
that point.
