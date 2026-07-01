# Every rental is for a title licensed in the renter's region

- **Signal:** a subscriber only ever rents a title that is licensed in their own
  region — joining `rentals` → `subscribers` (region) → `title_availability`, every
  rental resolves to a locally-available title.
- **Tables:** `rentals.title_id`, `rentals.subscriber_id`, `subscribers.region`,
  `title_availability.title_id`, `title_availability.region`
- **Magnitude:** exactly 0 rentals fall outside the renter's regional catalogue
  (100% locally licensed).

This is the collection's cross-table constraint: rentals are drawn only from the
titles available in the subscriber's market, so licensing is respected end to end.
It's a natural three-table anti-join question ("find rentals of an unlicensed
title") whose answer key is empty, and the setup for "which titles could this
subscriber *not* have rented?".

## How to find it

```sql
-- Rentals of a title NOT licensed in the renter's region → none.
select count(*)
from rentals rt
join subscribers s using (subscriber_id)
where not exists (
    select 1 from title_availability ta
    where ta.title_id = rt.title_id
      and ta.region   = s.region
);                                        -- 0
```
