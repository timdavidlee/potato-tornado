# The Kitchen owns the overtime tail

- **Signal:** for staff who showed up, `worked_hours >= planned_hours` always, and
  the overtime (`worked_hours - planned_hours`) is right-skewed everywhere. But the
  long tail is **not spread evenly across departments** — the **Kitchen** runs long
  far more often than the rest of the org, so it dominates total overtime hours.
- **Tables:** `time_entries.worked_hours`, `time_entries.planned_hours`,
  `shifts.department_id` → `departments.name` (join on `shift_id`)
- **Magnitude:** mean overtime ≈ **0.88 h** in the Kitchen vs ≈ **0.25 h** in every
  other department (~3.5×); ~**37%** of Kitchen shifts run 1 h+ over vs ~3%
  elsewhere. The Kitchen is ~14% of worked shifts but ~**36%** of all overtime
  hours. Overall overtime still skews right (mean ≈ 0.34 h > median ≈ 0.15 h).

Overtime is a non-negative draw added to planned hours, so a worked shift never
comes in *under* plan and the distribution has a spike at zero with a right tail —
the classic "most shifts are fine, a few blow out" shape. The teaching point is
that the blow-outs concentrate in one department: plotting overtime pooled looks
merely skewed, but grouping by department reveals the Kitchen as the driver. It's
the setup for a "where is overtime spend going?" question — the answer is one
cost centre, not the average.

## How to find it

```sql
-- overtime is right-skewed overall (mean > median)...
select avg(worked_hours - planned_hours)                     as mean_ot,   -- ≈ 0.34
       median(worked_hours - planned_hours)                  as med_ot     -- ≈ 0.15
from time_entries where not no_show;

-- ...but the tail belongs to the Kitchen
select d.name,
       count(*)                                              as shifts,
       avg(t.worked_hours - t.planned_hours)                 as mean_ot,   -- Kitchen ≈ 0.88, rest ≈ 0.25
       avg((t.worked_hours - t.planned_hours > 1.0)::int)    as share_1h   -- Kitchen ≈ 0.37, rest ≈ 0.03
from time_entries t
join shifts s using (shift_id)
join departments d using (department_id)
where not t.no_show
group by d.name
order by mean_ot desc;                 -- Kitchen on top by a wide margin
```
