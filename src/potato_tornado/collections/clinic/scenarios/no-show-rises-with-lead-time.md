# No-shows rise with booking lead time

- **Signal:** the further ahead an appointment is booked, the more likely it is a
  no-show — short-notice bookings are almost always kept, long-lead ones are missed
  far more often.
- **Tables:** `appointments.status`, `appointments.lead_days`
- **Magnitude:** no-show rate climbs from ≈ 9–10% for same-week bookings
  (`lead_days` < 15) to ≈ 22% for bookings made 45+ days out — roughly a 2× spread.
  The marginal no-show rate across all appointments stays ≈ 12%
  (see [`no-show-rate.md`](no-show-rate.md)).

This is the operational "why" behind the headline no-show rate: it isn't uniform.
A patient who books a slot two months out has more time for life to get in the way,
forget, or double-book. Surfacing the lead-time gradient is the setup for an
intervention question — e.g. would reminder calls or shorter booking horizons for
high-risk slots reduce missed capacity? Bucket by `lead_days` and watch the no-show
share climb.

## How to find it

```sql
select
    (lead_days / 15) * 15         as lead_bucket,   -- 0, 15, 30, ...
    count(*)                       as appts,
    avg((status = 'no_show')::int) as no_show_rate  -- rises: ~0.10 -> ~0.22
from appointments
group by lead_bucket
order by lead_bucket;
```
