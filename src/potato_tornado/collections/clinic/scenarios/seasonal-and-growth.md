# Appointment volume has a winter peak and grows year over year

- **Signal:** booked appointment volume is not flat across the three-year window —
  it rises in the winter respiratory-illness months and dips in summer, and the
  overall level drifts upward year over year as the clinic's panel grows.
- **Tables:** `appointments.scheduled_at` (equivalently `slots.slot_at`), `appointments.status`
- **Magnitude:** winter (Dec–Feb) monthly volume runs ≈ 24–35% above the summer
  (Jun–Aug) trough, repeating in each of the three calendar years; and volume drifts
  upward at ≈ +8%/year, so year 3 runs ≈ 13–23% above year 1 (an upward trend, noisy
  from year to year). The marginal lifecycle mix (no_show ≈ 12%, etc.) is unchanged —
  only the *count* of appointments moves with the calendar.

The clinic's demand is seasonal and growing, and a schedule sized for the summer
trough will be underwater every January. This is the temporal scenario the collection's
three-year window exists to support: it lets a student decompose a volume series into
trend + seasonality and reason about staffing to the peak vs. the average. The generator
draws each slot's day with a per-day weight (`_calendar_weights` in `tables/slots.py`) —
a winter-peaking seasonal cosine times an exponential year-over-year trend — instead of
uniformly. Because appointments book real slots, that biased `slots.slot_at` carries
straight through to `appointments.scheduled_at`; booking is season-independent, so the
lifecycle mix and per-slot utilisation are unchanged.

## How to find it

```sql
-- Monthly booked volume: winter months sit above summer, and the level climbs across years.
select
    date_trunc('month', scheduled_at)   as month,
    count(*)                            as appts
from appointments
group by month
order by month;                          -- Dec/Jan peaks ~1.25-1.30x the Jul trough; year 3 > year 1

-- Year-over-year:
select
    extract(year from scheduled_at)     as yr,
    count(*)                            as appts   -- ~ +8%/yr
from appointments
group by yr
order by yr;
```
