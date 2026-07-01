# Roughly one appointment in eight is a no-show

- **Signal:** appointment outcomes split ~68% completed / ~12% no-show /
  ~12% cancelled / ~8% still scheduled — no-shows are a small but material slice.
- **Tables:** `appointments.status`
- **Magnitude:** `no_show` ≈ 12% of all appointments.

The no-show rate is the clinic's core operational signal: a missed appointment is
capacity that was booked but wasted. An analyst should be able to read the
lifecycle mix off `status` directly, and (once slots/visits land) tie the no-show
rate to booking lead time. It's the natural setup for a utilisation question.

## How to find it

```sql
select status, count(*) * 1.0 / sum(count(*)) over () as share
from appointments
group by status;                     -- no_show ≈ 0.12
```
