# Parental leave is rare but dominates total leave hours

- **Signal:** parental leave is one of the *least* common leave types by spell
  count (~8% of `time_off` rows), yet it accounts for roughly **half of all leave
  hours** — more than vacation, which is over five times as common. Counting leave
  records and summing leave hours rank the leave types in nearly opposite orders.
- **Tables:** `time_off.leave_type`, `time_off.hours` (and
  `time_off.start_date` / `time_off.end_date` for the day span).
- **Magnitude (already produced; measured at seed=7):** parental is ≈ **7–8% of
  spells** but ≈ **50–53% of total leave hours** (≈50.5% at `scale=0.5`, ≈53.3% at
  `scale=1.0`). Its median spell runs ~**45 days** versus vacation ~5, unpaid ~7,
  and sick / holiday ~2 — roughly a **9–23×** longer spell than the everyday leave
  types. Vacation is the most common type (~42% of rows) but only ~30% of hours;
  sick is ~31% of rows but ~9% of hours.

Each `time_off` row is one leave spell, and `hours` is the paid time that spell
consumes. Because per-type spell length is drawn from a right-skewed lognormal
whose median is set by leave type (`_MEDIAN_DAYS`: parental 45, unpaid 7,
vacation 4, sick/holiday 1), a single parental spell is worth a dozen vacations.
So a naive "which leave type is most common?" (count rows) points at vacation and
sick, while "which leave type costs the most availability?" (sum hours) points at
parental. The teaching point is the count-vs-magnitude trap: ranking a categorical
by row count silently mis-weights a heavy-tailed measure, and for the utilization
denominator (available = capacity − leave) it is the *hours*, not the spell count,
that matter. It's the leave-side counterpart to the slice/concentration stories
elsewhere in the collection (`scenarios/no-show-rate.md`,
`scenarios/off-site-staffing-by-location.md`) — a flat top-line ("everyone takes
leave") that concentrates sharply once you weight by magnitude.

**Current state:** already produced by `tables/time_off.py`; no tuning needed. The
leave-type mix (`_LEAVE_TYPE_WEIGHTS`) and the per-type median spell lengths
(`_MEDIAN_DAYS`) together create the count-vs-hours inversion as an emergent
property. The realism guidance documents the leave mix and per-type medians as a
distribution, but the hours-concentration inversion is not yet called out as a
signal — this doc is the answer key for it. (Its natural partner surprises —
parental leave clustering by practice or season, or leave correlating with
attrition — stay flat and remain future scenarios.)

## How to find it

```sql
-- rank leave types by record count vs by total hours: the orders nearly invert.
-- parental is a small share of spells but the largest share of hours.
select leave_type,
       count(*)                                              as spells,
       count(*) * 1.0 / sum(count(*)) over ()                as count_share,  -- parental ~0.08
       sum(hours)                                            as leave_hours,
       sum(hours) * 1.0 / sum(sum(hours)) over ()            as hours_share,  -- parental ~0.50
       median(date_diff('day', start_date, end_date) + 1)    as median_days   -- parental ~45, sick ~2
from time_off
group by leave_type
order by hours_share desc;   -- parental on top by hours (~50%), yet near the bottom by count

-- the same inversion as one number: parental's hours-share is ~6x its count-share
select sum(hours) filter (where leave_type = 'parental') * 1.0 / sum(hours)   as parental_hours_share,  -- ~0.50-0.53
       avg((leave_type = 'parental')::int)                                    as parental_count_share    -- ~0.07-0.08
from time_off;
```
