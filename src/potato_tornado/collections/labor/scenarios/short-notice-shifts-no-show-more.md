# Short-notice shifts get missed more

- **Signal:** no-shows run at ~4% overall, but the rate is not uniform across the
  *scheduling lead time* either — a shift rostered at the last minute is missed
  far more often than one published a week or more ahead. Lead time is a second,
  independent lever on attendance alongside the shift window.
- **Tables:** `time_entries.no_show`, `assignments.assigned_at`,
  `shifts.planned_start` (lead time = `planned_start − assigned_at`; join
  `assignments`→`shifts` on `shift_id` and `assignments`→`time_entries` on
  `assignment_id`)
- **Magnitude (planted; measured at seed=7, scale=0.5):** short-notice shifts
  (lead `< 3` days) ≈ **8.1%** no-show vs comfortably-scheduled shifts (lead
  `≥ 7` days) ≈ **2.8%** — a **~2.9×** lift (the band gradient is monotone: <3d
  8.1% → 3–7d 5.8% → 7–14d 3.2% → ≥14d 1.9%) — while the marginal no-show rate
  across all entries stays ≈ **4.6%** (unchanged from the pre-plant 4.5%). Lead
  time and shift window compose multiplicatively, so a **night + short-notice**
  shift is the worst case (≈12%) and the two slice stories
  (`scenarios/no-show-rate.md`, night ≈8% still ~2.8× day) hold jointly.

Every assignment produces exactly one `time_entries` row, and each assignment now
carries an `assigned_at` (when the roster was published), so the scheduling lead
time `planned_start − assigned_at` is observable per shift. The teaching point is
that the flat "4% no-show" hides a *second* risk axis beyond the shift window:
people are likelier to miss a shift they only found out about at the last minute.
It sets up a multivariate question — is the night-shift no-show gradient really
about the *time of day*, or partly about the fact that night shifts get scheduled
on shorter notice? Controlling for one factor while reading the other is the
lesson. (As with the window signal, no-show rows are exactly the null-`clock_in`
rows, so "missing clock-in" and "no-show" are the same population.)

**Current state:** planted in `time_entries.py`. The per-row no-show probability
is the shift-window base (`_NO_SHOW_BY_WINDOW`) times a lead-time factor
`clip(7.0·exp(−lead_days/1.75) + 0.70, 0.70, 4.8)`, where `lead_days =
planned_start − assigned_at` comes from the assignments↔shifts join. The factor
decays from a last-minute cap (4.8×) down to a 0.70× floor for long-planned
shifts, so short-notice shifts are amplified and well-planned ones suppressed
relative to the window base; it averages ≈1.1 across the roster, so the marginal
holds ≈4.6% (≈ the pre-plant rate). Because lead time is drawn independently of
the shift window, the composition is multiplicative and the night/day ratio is
untouched. Only the no-show *threshold* changes — the `attendance` uniform draws
are unchanged, so determinism and the null-clock invariant both hold.

## How to find it

```sql
-- no-show rate by scheduling lead-time band; short notice should run highest.
-- (join assignments -> shifts for planned_start, assignments -> time_entries for no_show)
select
  case
    when date_diff('day', a.assigned_at, s.planned_start) < 3  then '0 <3d (short-notice)'
    when date_diff('day', a.assigned_at, s.planned_start) < 7  then '1 3-7d'
    when date_diff('day', a.assigned_at, s.planned_start) < 14 then '2 7-14d'
    else '3 >=14d'
  end                                          as lead_band,
  count(*)                                     as entries,
  avg(t.no_show::int)                          as no_show_rate   -- <3d ~0.08-0.09, >=7d ~0.03
from assignments a
join shifts       s using (shift_id)
join time_entries t using (assignment_id)
group by lead_band
order by lead_band;                            -- monotone: shortest lead on top

-- the two axes are independent: crossing window x lead band, night+short-notice is worst
select s.shift_window,
       date_diff('day', a.assigned_at, s.planned_start) < 3 as short_notice,
       avg(t.no_show::int)                                  as no_show_rate
from assignments a
join shifts       s using (shift_id)
join time_entries t using (assignment_id)
group by s.shift_window, short_notice
order by no_show_rate desc;                    -- night + short-notice tops the table
```
