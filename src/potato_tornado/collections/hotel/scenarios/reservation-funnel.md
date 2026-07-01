# Only honoured reservations become stays

- **Signal:** reservations split ~82% honoured / ~14% cancelled / ~4% no-show,
  and there is exactly one `stays` row per honoured reservation — cancelled and
  no-show bookings never appear in `stays`.
- **Tables:** `reservations.status`, `stays.reservation_id`
- **Magnitude:** `stays` row count ≈ 82% of `reservations`.

This is the collection's core funnel: a booking is intent, a stay is realisation.
An analyst joining `stays` back to `reservations` should find every stay maps to a
`status = 'honoured'` reservation, and that the drop-off (cancel + no-show) is
~18%. It's the natural setup for a conversion-rate question.

## How to find it

```sql
select status, count(*) from reservations group by status;   -- 0.82 / 0.14 / 0.04

select r.status                          -- every matched status is 'honoured'
from stays s join reservations r using (reservation_id)
group by r.status;
```
