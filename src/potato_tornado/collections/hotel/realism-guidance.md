# Realism guidance — hotel

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **A stay implies an honoured reservation.** `stays` rows exist only for reservations with
  `status = 'honoured'`; `cancelled` / `no_show` reservations never produce a stay.
- **Booking arithmetic.** `check_in_date = booked_date + lead_days` with
  `lead_days ∈ [0, 240]`; `check_out_date = check_in_date + nights`; `nights ∈ [1, 21]`;
  `party_size ∈ [1, 6]`.
- **Stay drifts, doesn't teleport.** `stays.actual_nights` differs from the reservation's
  `nights` by at most −2 (early checkout) to +3 (extension), and is ≥ 1;
  `room_revenue = nightly_rate × actual_nights` exactly.
- **Every property offers the full ladder.** `room_types` has all four types per property;
  `nightly_rate = base × location_multiplier` with a 0.7× floor, so rates stay positive and
  keep the Standard < Deluxe < Suite < Penthouse ordering.
- **Occupancy is bounded.** `demand_forecast.actual_occupied_rooms ≤ total_rooms`; forecast
  is the actual perturbed by multiplicative noise (Normal(1.0, `sd`) with `sd`=0.09 on
  weekdays, 0.22 on weekends) and clipped to `[0, total_rooms]`; exactly one row per property
  per day across the config span.
- **Service orders sit inside their stay.** Each `service_orders` row references a real
  `stay_id`, its `service_date` falls within the stay, and
  `amount = unit_price × quantity`.
- **Stay changes match the drift.** Each `stay_changes` row explains a non-zero gap
  between booked and realised nights: `nights_delta = actual_nights − booked_nights` is
  never 0, `change_type = 'early_checkout'` iff `nights_delta < 0` and `'extension'` iff
  `> 0`, and `actual_nights` agrees with the row's `stays` record. `fee > 0` in both cases
  (a flat one-night penalty for early checkout; a premium on the extra nights for
  extension) and is *separate* from `stays.room_revenue`, not a re-billing of it.
- **Upgrades move up the ladder.** Each `room_upgrades` row has `to_room_type` strictly
  above `from_room_type` in the Standard→Penthouse order; a Penthouse stay never appears as
  a `from_room_type` (it's already the top). `rate_delta > 0` is the property's rack-rate
  gap between the two classes, and `upgrade_fee < rate_delta × nights` always (the fee is a
  discounted slice of the gap, never the whole gap).
- **Referential integrity.** `reservations.property_id ∈ properties`,
  `stays.reservation_id ∈ reservations` (honoured), and `room_types` / `service_orders` /
  `room_upgrades` FKs resolve (`room_upgrades.stay_id ∈ stays`).

## Distributions & mixes (should look like the real world)

- **Channel mix.** Overall ota ≈0.43 (largest) / direct ≈0.34 / corporate ≈0.17 / walk_in
  ≈0.06, but keyed to room class: upper tiers (Suite/Penthouse) draw direct 0.55 / ota 0.22 /
  corporate 0.18 / walk_in 0.05, lower tiers direct 0.28 / ota 0.50 / corporate 0.16 /
  walk_in 0.06 — so direct is modal for the upper tiers. See
  `scenarios/ota-is-the-largest-channel.md`.
- **Room-type mix & rate ladder.** Standard 0.55 ($95) → Deluxe 0.28 ($145) → Suite 0.12
  ($260) → Penthouse 0.05 ($480), before the per-property location multiplier.
- **Reservation status.** honoured 0.82 / cancelled 0.14 / no_show 0.04.
- **Lead time.** Lognormal, median ≈14 days, right-skewed out to the 240-day cap.
- **Length & party.** `nights` ~ Poisson(2.2)+1; `party_size` ~ Poisson(1.3)+1.
- **Ancillary spend scales with stay.** Service-order count ~ Poisson(0.9 × nights) — longer
  stays accrue more entries. The catalog mixes discretionary spend (Breakfast, Spa, Dining,
  Room Service, Minibar, Laundry) with recurring stay fees (Internet, Television, Parking).
- **Upgrades are a discounted upsell.** ~15% of eligible stays upgrade (Penthouse stays
  excluded); most jump one rung (80%), occasionally two; the fee is 55–80% of the rack-rate
  delta (mean ≈0.68). See `scenarios/upgrades-are-a-discounted-upsell.md`.
- **Stays extend more than they shorten.** ~20% of stays are amended; of those, extensions
  outnumber early checkouts ~1.7:1. Early checkouts cut 1–2 nights (flat one-night penalty);
  extensions add 1–3 nights (10–25% premium). See
  `scenarios/extensions-outnumber-early-checkouts.md`.
- **Location pricing.** Per-property nightly-rate multiplier ~ Normal(1.0, 0.12).

## Deliberate simplifications (intended — do not "fix")

- Six properties, one per city, capped at the `CITIES` catalog length.
- The forecast is `actual × noise` with **no systematic bias** (it tracks actual by
  construction, only the error *magnitude* varies by weekday/weekend) and no real forecasting
  model — see `scenarios/forecast-tracks-actual-with-error.md`.
- **No seasonality or weekday/weekend rate variation** — nightly *rates* are flat over the
  calendar (only the forecast error band varies by weekend, not price). (A strong candidate to
  promote into a new scenario.)
- Status and room type are drawn independently, and channel depends only on room class (no
  channel-driven cancellation effects).
- Guests are not deduplicated: every reservation is a fresh name, so there is no
  repeat-guest / loyalty signal.
- Recurring fees (Internet, Television, Parking) are modeled as discretionary
  `service_orders` lines drawn ~Poisson(nights), not mandatory per-night folio charges — so
  a stay may show zero or several, rather than exactly one per night.
- Bookings aren't constrained by physical room inventory; only `demand_forecast` occupancy is
  capped at `total_rooms`.

## How to review

```sql
-- OTA is the largest channel (≈ 0.44)
select channel, count(*) * 1.0 / sum(count(*)) over () as share
from reservations group by channel order by share desc;    -- ota on top

-- stays exist only for honoured reservations: expect 0
select count(*) from stays s
join reservations r using (reservation_id)
where r.status <> 'honoured';                               -- expect 0

-- occupancy never exceeds capacity: expect 0
select count(*) from demand_forecast f
join properties p using (property_id)
where f.actual_occupied_rooms > p.total_rooms;              -- expect 0

-- room revenue reconciles: expect 0 mismatches
select count(*) from stays
where round(nightly_rate * actual_nights, 2) <> room_revenue;  -- expect 0
```
