# No-shows are rare but leave a clear trace

- **Signal:** ~4% of rostered assignments end in a no-show; a no-show row has a
  null `clock_in` / `clock_out` / `worked_hours` and `no_show = true`.
- **Tables:** `time_entries.no_show`, `time_entries.clock_in`, `assignments`
- **Magnitude:** ~4% of `time_entries` (attendance is Bernoulli p=0.96).

Every assignment produces exactly one `time_entries` row, so the no-show rate is
just the share of rows with `no_show = true`. Those rows are the only ones with
null clock times — a student learning about null handling should discover that
"missing clock-in" and "no-show" are the same population, not two separate issues.

## How to find it

```sql
select avg(no_show::int) as no_show_rate,           -- ≈ 0.04
       count(*) filter (where clock_in is null) as null_clock_ins
from time_entries;                                   -- null_clock_ins == no-show count
```
