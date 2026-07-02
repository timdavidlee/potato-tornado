# Realism guidance — logistics

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** `shipments.warehouse_id ∈ warehouses`,
  `shipments.carrier_id ∈ carriers`, `scan_events.shipment_id ∈ shipments`,
  `deliveries.shipment_id ∈ shipments`.
- **`deliveries` is 1:1 with `shipments`.** `deliveries.height == shipments.height` and
  `shipment_id` is unique in each — every parcel has exactly one terminal outcome.
- **Scan timelines are ordered.** Within a shipment, `scan_events` rows have strictly
  increasing `scan_ts` matching `seq` (1..k, contiguous). The first scan is on/after
  `ship_date`; the terminal scan is the max `seq`.
- **Dates are ordered.** `promised_date = ship_date + promised transit days ≥ ship_date`;
  for delivered parcels `actual_delivery_date ≥ ship_date`.
- **Terminal consistency (no third state).** `status = 'delivered'` ⇔ the terminal scan is
  `delivered` ⇔ `actual_delivery_date` and `days_late` are both non-null. A non-delivered
  status ⇔ the terminal scan is `exception` ⇔ both are null. `returned_to_sender` reached
  `out_for_delivery` before the exception; `lost` never did — that structural difference is
  how `deliveries` recovers the status, so it can never disagree with the scans.
- **Arithmetic identities.** `days_late = actual_delivery_date − promised_date` (signed, in
  days) for delivered parcels; `shipping_cost = round((base_rate + weight_kg × per_kg_rate +
  dest_zone × 1.25) × price_multiplier, 2)`.
- **Non-negativity / bounds.** `weight_kg ∈ (0, 50]`, `shipping_cost > 0`,
  `dest_zone ∈ [1, 8]`, `attempts ∈ [1, 3]`, `seq ≥ 1`, `reliability ∈ (0, 1)`.
- **Catalogs are fixed.** `service_level ∈ {ground, express, overnight}`;
  `scan_type ∈ {picked_up, in_transit, out_for_delivery, delivered, exception}`;
  `status ∈ {delivered, returned_to_sender, lost}`; `warehouses.region` from the 4-region set.

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `carriers` = 5, `warehouses` = 12, `shipments` = 8000,
  `deliveries` = 8000 (1:1), `scan_events` ≈ 3–6 × shipments (variable length).
- **Service mix.** ground 0.70 / express 0.22 / overnight 0.08; promised transit ground 5d,
  express 2d, overnight 1d. Faster tiers cost more (multipliers 1.0 / 1.6 / 2.5) and are rarer.
- **weight_kg.** Lognormal, median ≈ 2 kg, σ ≈ 0.8, clamped to [0.1, 50] — most parcels
  light, a long heavy tail.
- **dest_zone.** Integers 1–8, weighted toward the middle (mode at zones 4–5) — most parcels
  travel a moderate distance, few very near or very far.
- **shipping_cost.** Right-skewed via the weight tail (not a second draw): median ≈ \$12,
  p95 ≈ \$27, max past \$80. `corr(weight_kg, shipping_cost)` ≈ 0.44 — weight is one of three
  drivers (with zone and the service multiplier). See `scenarios/shipping-cost-right-skew.md`.
- **ship_date.** Uniform across the full ~3-year window (no clustering, no seasonality).
- **scan count.** 4 on the happy path (`picked_up → in_transit → out_for_delivery →
  delivered`); +1 `in_transit` hop for zones ≥ 5 (and a second past zone 7); a non-delivered
  parcel ends in `exception` instead of `delivered` (returned reaches `out_for_delivery`
  first, lost does not) — so ≈ 3–6 rows/shipment.
- **on-time rate.** Overall ≈ 86% of delivered parcels on time (`days_late ≤ 0`), declining
  from ≈ 0.96 at zone 1 to ≈ 0.75 at zone 8. On-time propensity blends carrier `reliability`
  (≈ 0.85–0.97) with a per-zone penalty. See `scenarios/on-time-degrades-with-zone.md`.
- **late tail.** The late minority (~14% of delivered) is right-skewed: mean ≈ +2.6 days,
  clamped to +7. Early arrivals (a small Poisson) pull overall mean `days_late` slightly
  below zero. See `scenarios/promised-vs-actual-late-tail.md`.
- **terminal status mix.** delivered ≈ 0.965 / returned_to_sender ≈ 0.025 / lost ≈ 0.010.
- **attempts.** ~0.82 of parcels take 1 attempt, then 2, rarely 3 — but skewed higher for the
  hard path (late or non-delivered): mean ≈ 1.2 attempts on the easy path vs ≈ 1.6 on the hard.

## Deliberate simplifications (intended — do not "fix")

- **One `deliveries` row per shipment** — no split shipments or multi-parcel orders.
- **Scan `location_city` is a coarse city label** (from `ctx.entities.cities`), not a
  facility code or lat/long; intermediate `in_transit` hub cities are synthetic and drawn per
  scan, unrelated to real geography between origin and destination.
- **`dest_zone` is a per-shipment distance proxy**, drawn directly — not computed from the
  warehouse's and destination's cities. `dest_city` and `warehouses.city` are independent
  labels; zone is the only distance signal.
- **Transit is measured in calendar days** — no weekend/holiday pauses, no business-day
  arithmetic. `promised_date` can land on any day of the week.
- **Flat `per_kg_rate`** — no dimensional/volumetric weight, fuel surcharges, customs, or
  zone-based per-kg pricing. Cost is a clean linear identity.
- **Attendance-style independence.** On-time, terminal status, early/late days and attempts
  are drawn independently per shipment — no per-carrier streaks, no seasonality, no weather,
  and no dependence of status on service level or weight.
- **Carrier `reliability` is a static dim attribute**, not learned from the parcel's own scan
  history; it only sets the on-time propensity prior.

## How to review

```sql
-- deliveries is 1:1 with shipments, and terminal status is consistent with the scans
select (select count(*) from deliveries) - (select count(*) from shipments) as row_gap;  -- 0

-- delivered ⇔ non-null actual/days_late; non-delivered ⇔ both null (expect 0 violations)
select count(*) filter (where status = 'delivered' and (actual_delivery_date is null
                                                        or days_late is null))
     + count(*) filter (where status <> 'delivered' and (actual_delivery_date is not null
                                                        or days_late is not null)) as bad_rows;  -- 0

-- cost matches the arithmetic identity for every shipment (expect 0)
select count(*) as mismatches
from shipments s join carriers c using (carrier_id)
where round((c.base_rate + s.weight_kg * c.per_kg_rate + s.dest_zone * 1.25)
            * case s.service_level when 'ground' then 1.0 when 'express' then 1.6 else 2.5 end,
            2) <> s.shipping_cost;

-- scan timestamps strictly increase with seq within each shipment (expect 0 out-of-order)
select count(*) as out_of_order from (
  select scan_ts < lag(scan_ts) over (partition by shipment_id order by seq) as bad
  from scan_events
) where bad;

-- on-time rate declines with zone (≈0.96 → ≈0.75)
select s.dest_zone, avg((d.days_late <= 0)::int) as on_time
from deliveries d join shipments s using (shipment_id)
where d.status = 'delivered' group by s.dest_zone order by s.dest_zone;
```
