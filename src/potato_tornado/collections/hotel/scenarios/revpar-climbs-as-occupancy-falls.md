# RevPAR climbs the ladder even as occupancy falls

- **Signal:** per-class **RevPAR** (revenue per *available* room-night) and per-class
  **occupancy** rank the four room classes in **opposite orders**. Occupancy falls down the
  ladder — Standards run hottest, Penthouses coolest
  (`scenarios/premium-rooms-run-cooler.md`) — but RevPAR rises *up* it: the Penthouse is the
  lowest-occupancy class and simultaneously the **highest-earning per available room**. The
  premium classes look like idle over-supply on occupancy alone, yet they out-yield the
  Standards once rate is folded in.
- **Tables:** `stays.room_revenue`, `stays.actual_nights`, `stays.room_type`,
  `room_types.room_count`, `room_types.room_type` (available room-nights =
  `room_count × window days`)
- **Magnitude:** RevPAR (`room_revenue ÷ available room-nights`) climbs monotonically —
  Standard ≈ **$8.1** < Deluxe ≈ **$12.3** < Suite ≈ **$16.3** < Penthouse ≈ **$22.8**, so
  the Penthouse earns ≈ **2.8×** the Standard *per available room*. Occupancy runs the other
  way (down the ladder, ≈0.070 → ≈0.039). The driver is ADR: it rises ≈ **5×** across the
  ladder (≈$116 / $178 / $318 / $580), which swamps the ≈1.8× occupancy shortfall at the top.
  (Numbers measured at the scenario-test config, seed=21, scale=0.5.)

This is the payoff to the question `scenarios/premium-rooms-run-cooler.md` deliberately leaves
open — "a premium room at low occupancy can still out-earn a full standard, so the fix isn't
obvious from occupancy alone." Here it is: it does, and by a wide margin. The teaching point is
that **occupancy is the wrong yardstick for yield**. A revenue manager who optimizes occupancy
would pour demand into Standards and read the empty Penthouses as a mistake; RevPAR — the
industry's headline metric precisely because it folds rate and occupancy into one number —
flips that conclusion. The two signals must be read together: `premium-rooms-run-cooler` says
*which rooms sit emptiest*, this one says *which rooms earn most per unit of capacity*, and
they disagree on purpose. (RevPAR here is net of tax: `room_revenue` is the net room charge, so
the wedge in `stays.taxes_fees` — see `scenarios/tax-load-lighter-in-iberia.md` — stays out of
it.)

## How to find it

```sql
-- occupancy vs RevPAR by class: they rank the four classes in opposite orders
with sold as (
  select room_type, sum(actual_nights) as nights_sold, sum(room_revenue) as rev
  from stays group by room_type
),
avail as (
  select room_type, sum(room_count) as rooms from room_types group by room_type
),
span as (
  select date_diff('day', min(check_in_date), max(check_in_date)) as days from reservations
)
select s.room_type,
       s.nights_sold * 1.0 / (a.rooms * span.days) as occupancy,   -- FALLS down the ladder
       s.rev / s.nights_sold                       as adr,         -- rises ≈5× up the ladder
       s.rev / (a.rooms * span.days)               as revpar       -- RISES up the ladder
from sold s
join avail a using (room_type), span
order by revpar;
-- Standard  occ ≈0.070  adr ≈116  revpar ≈8.1
-- Deluxe    occ ≈0.069  adr ≈178  revpar ≈12.3
-- Suite     occ ≈0.051  adr ≈318  revpar ≈16.3
-- Penthouse occ ≈0.039  adr ≈580  revpar ≈22.8   (lowest occupancy, highest RevPAR)
```
