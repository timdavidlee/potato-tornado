# Guests extend more often than they leave early

- **Signal:** most stays run exactly as booked; among those that don't, **extensions
  outnumber early checkouts** (~1.7:1). Early checkouts carry a flat one-night penalty;
  extensions carry a percentage premium on the extra nights.
- **Tables:** `stay_changes.change_type`, `stay_changes.nights_delta`, `stay_changes.fee`
- **Magnitude:** ~**20%** of stays are amended; of those, extensions ≈ **62%** vs early
  checkouts ≈ 38% (≈1.7×). Early leave 1–2 nights early; extensions add 1–3 nights.

A stay-change is its own event, derived from the gap between the reservation's booked
nights and the realised `stays.actual_nights`. The teaching point is twofold: the
directional asymmetry (people extend more than they cut short), and that the *fee* is not
the room charge — early-departure is a flat penalty, an extension is a small premium layered
on top of the extra room nights (which are already in `stays.room_revenue`).

## How to find it

```sql
-- amendment mix: extensions clearly outnumber early checkouts
select change_type, count(*) as n,
       count(*) * 1.0 / sum(count(*)) over () as share
from stay_changes group by change_type;          -- extension ≈ 0.62, early_checkout ≈ 0.38

-- and only ~20% of stays are amended at all
select count(*) * 1.0 / (select count(*) from stays) as amend_rate   -- ≈ 0.20
from stay_changes;
```
