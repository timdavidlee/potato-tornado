# Night shifts drive the no-show rate

- **Signal:** no-shows run at ~4% overall, but the rate is not uniform across the
  day — **night shifts are missed far more often** than morning or afternoon ones.
  The headline 4% is a blend of a low daytime rate and a much higher night rate.
- **Tables:** `time_entries.no_show`, `shifts.shift_window` (join on `shift_id`)
- **Magnitude:** night ≈ **8%** vs morning/afternoon ≈ **2%** — roughly a **4×**
  spread — while the marginal no-show rate across all entries stays ≈ 4%.

Every assignment produces exactly one `time_entries` row, so the overall no-show
rate is just the share of rows with `no_show = true`. The teaching point is that a
flat "4% no-show" hides where the risk actually sits: bucket by the shift's
`shift_window` and the night window stands out as the operational problem to fix.
It's the setup for a staffing / reminder-intervention question — which shifts
should get the attention? (Those no-show rows are also the only ones with null
`clock_in` / `clock_out`, so "missing clock-in" and "no-show" are the same
population, not two separate issues.)

## How to find it

```sql
-- overall rate ≈ 0.04, but it splits sharply by shift window
select s.shift_window,
       count(*)                        as entries,
       avg(t.no_show::int)             as no_show_rate   -- night ~0.08, day ~0.02
from time_entries t
join shifts s using (shift_id)
group by s.shift_window
order by no_show_rate desc;            -- night on top, ~4x the day windows

select avg(no_show::int) as overall,                     -- ≈ 0.04
       count(*) filter (where clock_in is null) as null_clock_ins  -- == no-show count
from time_entries;
```
