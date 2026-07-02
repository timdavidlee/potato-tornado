# Booking lead time is right-skewed

- **Signal:** the gap between `booked_date` and `check_in_date` is right-skewed — most
  bookings are made a week or two out, but a long tail books months ahead, so the mean sits
  well above the median.
- **Tables:** `reservations.booked_date`, `reservations.check_in_date`
- **Magnitude:** lead days are lognormal — median ≈ **14**, mean ≈ **20**, p95 ≈ **59**,
  hard-capped at **240**. Mean > median is the tell-tale of the right skew.

Lead time is drawn `lognormal(median=14, sigma=0.9)` and clipped to `[0, 240]`. The teaching
point is distribution shape: a student computing only the average books-ahead window (≈20
days) overstates the typical guest, who books ≈14 days out. The median/mean gap and the long
upper tail are the lesson — reach for the median (or a full percentile spread) on skewed
duration data, not the mean.

## How to find it

```sql
-- lead time is right-skewed: mean sits above the median, tail runs to the 240 cap
select
  median(date_diff('day', booked_date, check_in_date)) as median_lead,   -- ≈ 14
  avg(date_diff('day', booked_date, check_in_date))    as mean_lead,      -- ≈ 20
  quantile_cont(date_diff('day', booked_date, check_in_date), 0.95) as p95_lead,  -- ≈ 59
  max(date_diff('day', booked_date, check_in_date))    as max_lead        -- ≤ 240
from reservations;
```
