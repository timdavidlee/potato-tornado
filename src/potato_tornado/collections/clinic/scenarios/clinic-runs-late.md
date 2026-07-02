# The clinic runs behind: arrival-relative delay grows through the day

- **Signal:** early-morning visits start close to on time, but delay accumulates as the
  day goes on — an appointment's realised start slips further behind schedule the later
  in the day it sits, the classic waiting-room cascade of a clinic that never quite
  catches up after it falls behind.
- **Tables:** `visits.arrival_delay_min`, `appointments.scheduled_at`
  (join `visits.appointment_id → appointments.appointment_id`)
- **Magnitude:** mean `arrival_delay_min` climbs monotonically with the scheduled hour,
  from ≈ −2 min for early-morning appointments (before 10:00, when the clinic is on time) to
  ≈ 11–13 min for late-afternoon (16:00+) ones — a ≈ 13-minute swing across the day. The
  overall mean stays ≈ 2–3 min.

Delay is not a property of the patient so much as of the queue: one over-running visit
(see [`procedure-efficiency.md`](procedure-efficiency.md)) pushes every appointment behind
it, and the effect compounds through the session. Surfacing the time-of-day gradient is the
setup for scheduling-policy questions — front-loading complex visits, building slack after
lunch, or capping afternoon double-bookings. `arrival_delay_min` is drawn around a mean that
grows linearly with the appointment's scheduled hour (`_ARRIVAL_SLOPE` / `_ARRIVAL_PIVOT_HOUR`
in `tables/visits.py`), pivoting near 9:00 so the clinic-wide mean stays ≈ 2–3 min while the
afternoon runs well behind. `visits` reads the hour from the completed appointment's
`scheduled_at`.

## How to find it

```sql
select
    extract(hour from a.scheduled_at)   as hr,
    count(*)                            as visits,
    avg(v.arrival_delay_min)            as mean_delay   -- climbs ~1 (early) -> ~12 (late)
from visits v
join appointments a on a.appointment_id = v.appointment_id
group by hr
order by hr;
```
