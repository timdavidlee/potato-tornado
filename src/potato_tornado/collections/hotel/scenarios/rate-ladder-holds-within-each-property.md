# The rate ladder holds within every property, but the same class varies by location

- **Signal:** inside any one property nightly rates are strictly ordered
  Standard < Deluxe < Suite < Penthouse; across the six properties the *same* class is
  scattered around its base rate by a per-property location multiplier.
- **Tables:** `room_types.nightly_rate`, `room_types.room_type`, `room_types.property_id`
- **Magnitude:** base ladder $95 / $145 / $260 / $480; per-property multiplier
  ~ Normal(1.0, 0.12) with a 0.7× floor, so a class's rate spreads ≈ **±12%** (coefficient of
  variation ≈ 0.11) across properties — e.g. Standard ranges ≈ $84–$115. The within-property
  ordering **never** inverts.

Every property offers all four classes; `nightly_rate = base × location_multiplier`. The
teaching point is two levels of price variation living in one column: the deterministic ladder
*within* a property, and the location noise *between* them. A student comparing raw rates
across the group must control for room class first — the cross-property dispersion is location,
not class.

## How to find it

```sql
-- within-property ordering is strict (expect 0 inversions)
select count(*) from (
  select property_id,
         max(case when room_type='Standard'  then nightly_rate end) as s,
         max(case when room_type='Deluxe'    then nightly_rate end) as d,
         max(case when room_type='Suite'     then nightly_rate end) as u,
         max(case when room_type='Penthouse' then nightly_rate end) as p
  from room_types group by property_id
) where not (s < d and d < u and u < p);        -- expect 0

-- same class disperses ≈ ±12% across properties by location
select room_type, min(nightly_rate), avg(nightly_rate), max(nightly_rate),
       stddev_samp(nightly_rate) / avg(nightly_rate) as cv     -- ≈ 0.11
from room_types group by room_type;
```
