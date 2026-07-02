# Lead time is right-skewed — and the tail is fattest for the OTA

- **Signal:** the gap between `booked_date` and `check_in_date` is right-skewed
  overall (mean well above median), but the skew is not uniform: **OTA** bookings
  book far ahead with a fat tail, while **walk_in** is same-/next-day and
  **direct**/**corporate** sit in between. The same median-vs-mean gap that shows
  up on the whole table is dramatically wider for the OTA than for direct.
- **Tables:** `reservations.channel`, `reservations.booked_date`, `reservations.check_in_date`
- **Magnitude:** overall median ≈ **13**, mean ≈ **24**, p95 ≈ **84**, capped at
  **240**. By channel — ota median ≈ **24** / mean ≈ **37** / p95 ≈ **121**;
  direct ≈ **12** / **17** / **47**; corporate ≈ **7** / **10** / **30**; walk_in
  ≈ **0** / **0.7** / **2**. OTA's mean is ~2× direct's; its p95 ~2.5×.

Lead time is drawn lognormal with a per-channel `(median, sigma)`
(`LEAD_TIME_BY_CHANNEL`) and clipped to `[0, 240]`. There are two nested lessons.
First, distribution shape: a student averaging the whole column (≈24 days)
overstates the typical guest, who books ≈13 days out — reach for the median (or a
percentile spread) on skewed duration data, not the mean. Second, the skew itself
is a segmentation story: pooling all channels hides that OTA leisure guests plan
weeks ahead (long tail) while walk-ins commit at the desk. "Book earlier" advice
is really "the OTA books early"; the mean is dragged up by that one channel's tail.

## How to find it

```sql
-- overall: right-skewed, mean sits above the median, tail runs toward the 240 cap
select
  median(date_diff('day', booked_date, check_in_date)) as median_lead,   -- ≈ 13
  avg(date_diff('day', booked_date, check_in_date))    as mean_lead,      -- ≈ 24
  quantile_cont(date_diff('day', booked_date, check_in_date), 0.95) as p95_lead,  -- ≈ 84
  max(date_diff('day', booked_date, check_in_date))    as max_lead        -- ≤ 240
from reservations;

-- the tail is fattest for the OTA, near-zero for walk_in
select channel,
  median(date_diff('day', booked_date, check_in_date)) as median_lead,
  avg(date_diff('day', booked_date, check_in_date))    as mean_lead,
  quantile_cont(date_diff('day', booked_date, check_in_date), 0.95) as p95_lead
from reservations group by channel order by mean_lead desc;
-- ota ≈24/37/121, direct ≈12/17/47, corporate ≈7/10/30, walk_in ≈0/0.7/2
```
