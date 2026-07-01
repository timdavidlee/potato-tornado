# Worked hours run over plan, with a right-skewed overtime tail

- **Signal:** for staff who showed up, `worked_hours >= planned_hours` always;
  the overtime (`worked_hours - planned_hours`) is small for most shifts but has
  a long right tail.
- **Tables:** `time_entries.worked_hours`, `time_entries.planned_hours`
- **Magnitude:** overtime is `max(0, Normal(0.15, 0.5))` hours — median near zero,
  mean ≈ 0.2 h, occasional multi-hour tails.

Overtime is modelled as a non-negative draw added to planned hours, so actual
never comes in *under* plan. An analyst plotting the overtime distribution should
see a spike at zero and a right-skewed tail — the classic shape of "most shifts
are fine, a few blow out." Mean overtime exceeds the median, the tell-tale sign
of right skew.

## How to find it

```sql
select worked_hours - planned_hours as overtime
from time_entries
where not no_show;                  -- histogram: spike at 0, long right tail
-- avg(overtime) > median(overtime)  → right-skewed
```
