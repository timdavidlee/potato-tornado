# Check-ins peak in summer, every year

- **Signal:** arrivals follow a repeating annual season — a summer peak (Jun–Aug) and a
  winter trough (Dec–Feb) — that recurs across all three calendar years in the window, rather
  than being spread flat over the calendar.
- **Tables:** `reservations.check_in_date` (and, downstream, `stays.actual_check_in` /
  `demand_forecast.actual_occupied_rooms`)
- **Magnitude:** a smooth cosine season peaking in **July** and bottoming in **winter**
  (Jan–Feb). Summer arrivals (Jun–Aug) run ≈ **1.6×** winter (Dec–Feb) — peak *month* ≈ 1.66×
  the trough month — and the same cycle repeats in each of the ~3 years in the window.

`check_in_date` is drawn from a day-of-year weight
`1 + 0.23·cos(2π·(doy − 196)/365.25)` (peak day-of-year ≈ mid-July), and `booked_date` is
backed out as `check_in − lead_days` so the seasonal peak lands cleanly on arrivals rather
than being smeared by lead time. Because the window spans ~3 years the same cycle repeats —
the natural setup for a year-over-year seasonality lesson (group by month-of-year to see the
shape, group by year×month to confirm it repeats). Occupancy in `demand_forecast` inherits
the peak because it is derived from stays.

## How to find it

```sql
-- arrivals by month-of-year: a clear summer bulge (Jun–Aug) vs winter trough (Dec–Feb)
select extract(month from check_in_date) as mo, count(*) as arrivals
from reservations
group by mo order by mo;      -- peak month (Jul) ≈ 1.66× the trough month (Feb)

-- and the cycle repeats each year (peak month leads every year)
select extract(year from check_in_date) as yr,
       extract(month from check_in_date) as mo,
       count(*) as arrivals
from reservations
group by yr, mo order by yr, arrivals desc;   -- summer months top each year
```
