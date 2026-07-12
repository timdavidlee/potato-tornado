# Weekend arrivals pay a rate premium — for the whole stay, not just the weekend nights

- **Signal:** stays that *arrive* Fri–Sun bill a ~10% higher nightly rate than stays that
  arrive Mon–Thu. The twist is *where* the premium lands: it keys off the **check-in day** and
  rides the single per-stay `nightly_rate` across **every** night of the stay — so a Saturday
  arrival pays the bump on its weekday nights too, while a Wednesday arrival that runs through
  the weekend pays nothing extra for those weekend nights.
- **Tables:** `stays.nightly_rate`, `stays.actual_check_in`, `stays.actual_nights`,
  `room_types.nightly_rate` (the flat rack rate, to normalise the billed rate against)
- **Magnitude:** billed-over-rack lift `stays.nightly_rate / room_types.nightly_rate` —
  weekend-arrival ≈ **1.12** vs weekday-arrival ≈ **1.02**, a ratio of ≈ **1.10** (the
  `_RATE_WEEKEND_LIFT` factor; the residual ~1.02 on weekday arrivals is the summer-season
  cosine, which averages out of the ratio). Raw ADR runs ≈ **$191** for weekend arrivals vs
  ≈ **$173** for weekday ones. ~**43%** of stays are weekend arrivals (arrivals are flat across
  the day of week, so ≈ 3/7). Among weekday arrivals the lift stays flat at ≈ **1.02** whether
  the stay spans **0, 1, 2, or 3** weekend nights — and ~**55%** of them *do* contain at least
  one weekend night. (Numbers measured at the scenario-test config, seed=21, scale=0.5.)

`stays.nightly_rate` is the **billed** rate, not the flat `room_types.nightly_rate` rack: it's
`rack × season × weekend`, where `weekend = 1.10` when `actual_check_in.weekday() >= 4` (Fri–Sun)
and `1.0` otherwise (see `_effective_rate` in `tables/stays.py`). Because the whole stay carries
one `nightly_rate`, the weekend factor is decided once — by the arrival day — and then multiplies
every night. The teaching point is the inversion of the naive model: an analyst assumes *weekend
nights* cost more and reaches for a per-night day-of-week breakdown, but the data prices *weekend
arrivals*, whole-stay. Grouping by check-in weekday reveals the ~10% premium cleanly; grouping by
which nights fall on a weekend reveals nothing. This is the day-of-*week* sibling of
`scenarios/check-ins-peak-in-summer.md` (the day-of-*year* season) — both live in
`stays.nightly_rate` and compound, so the top billed rate is a summer weekend arrival — and it
sits under the ADR that drives `scenarios/revpar-climbs-as-occupancy-falls.md`. The invariant
`room_revenue = nightly_rate × actual_nights` is untouched: the premium is already inside
`nightly_rate`.

## How to find it

```sql
-- weekend-arrival stays bill ~10% above weekday-arrival stays (rack-normalised)
-- DuckDB dayofweek: Sun=0 .. Sat=6, so a Fri/Sat/Sun arrival is dayofweek in (5, 6, 0)
select case when dayofweek(s.actual_check_in) in (5, 6, 0) then 'weekend' else 'weekday' end
         as arrival_kind,
       avg(s.nightly_rate / rt.nightly_rate) as mean_lift,   -- weekend ~1.12, weekday ~1.02
       sum(s.room_revenue) / sum(s.actual_nights) as adr     -- weekend ~$191, weekday ~$173
from stays s
join room_types rt using (property_id, room_type)
group by arrival_kind order by mean_lift desc;
-- weekend mean_lift ~1.12 / adr ~191, weekday ~1.02 / adr ~173  (ratio ~1.10)

-- the twist: for WEEKDAY (Mon-Thu) arrivals the lift is flat no matter how many nights
-- actually fall on a weekend -- so the premium keys off the arrival day, not the weekend nights
with weekday_arrivals as (
  select s.stay_id,
         s.nightly_rate / rt.nightly_rate as lift,
         (select count(*) from range(s.actual_nights) g(o)
          where dayofweek(s.actual_check_in + g.o) in (5, 6, 0)) as weekend_nights
  from stays s
  join room_types rt using (property_id, room_type)
  where dayofweek(s.actual_check_in) not in (5, 6, 0)   -- Mon-Thu arrivals only
)
select weekend_nights, avg(lift) as mean_lift, count(*) as stays
from weekday_arrivals group by weekend_nights order by weekend_nights;
-- mean_lift ~1.02 across weekend_nights = 0, 1, 2, 3 -- weekend nights add nothing to the rate
```
