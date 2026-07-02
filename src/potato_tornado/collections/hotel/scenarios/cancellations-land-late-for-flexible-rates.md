# Flexible-rate cancellations land late; non-refundable ones land early

- **Signal:** among cancelled bookings, *when* the cancellation happens depends on the rate
  plan. Flexible **BAR** guests cancel **late** in the booking window — on average only ~10
  days before arrival, ~61% of the way from booking to check-in — because they can walk away
  for free at the last minute. Non-refundable **Advance-Purchase** guests cancel **early** —
  ~24 days out, only ~23% into the window: if you're going to eat the cost, you do it as soon
  as plans change. `cancellation_date` is **null** for every booking that wasn't cancelled
  (honoured *and* no_show — a no-show never cancels, it just fails to arrive).
- **Tables:** `reservations.rate_plan`, `reservations.status`, `reservations.cancellation_date`,
  `reservations.booked_date`, `reservations.check_in_date`
- **Magnitude:** share of the booking window elapsed before the cancellation — BAR ≈0.61 >
  Package ≈0.45 > Corporate-negotiated ≈0.39 > Advance-Purchase ≈0.23. As days before
  arrival, Advance-Purchase leads by ≈24 (median 14) vs BAR ≈10 (median 5). ~12% of all
  bookings carry a `cancellation_date`; the other ~88% are null.

This is the timing half of the rate-plan story in
`scenarios/non-refundable-rates-cancel-less.md`: non-refundable fares not only cancel *less*,
the few that do cancel land *earlier*, which is exactly the shape that lets a hotel re-sell the
room. It's also the collection's first **nullable** column, so it doubles as a NULL-handling
teaching case: any "cancellation lead time" query has to filter to
`status = 'cancelled'` (or `cancellation_date is not null`) or the nulls poison the average.

## How to find it

```sql
-- window fraction elapsed before cancelling, by rate plan (flexible cancels latest)
select rate_plan,
       avg(date_diff('day', booked_date, cancellation_date) * 1.0
           / nullif(date_diff('day', booked_date, check_in_date), 0)) as window_frac
from reservations
where status = 'cancelled'
group by rate_plan order by window_frac desc;
-- BAR ≈0.61, Package ≈0.45, Corporate-negotiated ≈0.39, Advance-Purchase ≈0.23

-- same story as days before arrival: non-refundable leads by more
select rate_plan, avg(date_diff('day', cancellation_date, check_in_date)) as days_before
from reservations
where status = 'cancelled'
group by rate_plan order by days_before desc;   -- Advance-Purchase ≈24 on top, BAR ≈10

-- the column is null unless the booking was cancelled
select status, count(*) filter (where cancellation_date is not null) as dated, count(*)
from reservations group by status;              -- only 'cancelled' rows are dated
```
