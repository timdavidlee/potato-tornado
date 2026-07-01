# Some visit types systematically run over their booked time

- **Signal:** realised visit duration vs. the booked slot length depends on the
  visit type — new-patient and minor-procedure visits run over, telehealth runs
  short, routine follow-ups land on time.
- **Tables:** `visits.actual_minutes`, `visits.scheduled_minutes`, `visits.visit_type`
- **Magnitude:** mean `actual / scheduled` ratio by type: Minor Procedure ≈ 1.20,
  New Patient ≈ 1.14, Chronic Care ≈ 1.10, Annual Physical ≈ 1.04, Follow-up ≈ 1.00,
  Telehealth ≈ 0.95.

Scheduling templates assume every visit fits its nominal slot, but some procedure
types reliably don't — and that overrun is what makes a clinic's day run late. An
analyst comparing booked vs. actual minutes by `visit_type` can see which templates
are mis-sized: if new-patient visits average 14% over, the 40-minute slot is too
short. It's the setup for a slot-length tuning question.

## How to find it

```sql
select
    visit_type,
    avg(scheduled_minutes)                          as booked_min,
    avg(actual_minutes)                             as actual_min,
    avg(actual_minutes) / avg(scheduled_minutes)    as ratio  -- 0.95 .. 1.20
from visits
group by visit_type
order by ratio desc;
```
