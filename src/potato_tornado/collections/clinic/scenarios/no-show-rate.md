# New Patient visits drive the no-show rate

- **Signal:** appointment outcomes split ~68% completed / ~12% no-show / ~12%
  cancelled / ~8% still scheduled overall — but the no-show slice is not spread
  evenly across visit types. **New Patient visits no-show far more than any other
  type**, well above the 12% marginal; established-care visit types (Annual
  Physical, Minor Procedure) sit below it.
- **Tables:** `appointments.status`, `appointments.visit_type`
- **Magnitude:** overall no-show ≈ 12%. New Patient ≈ **20–23%** vs Annual
  Physical / Minor Procedure ≈ 8–9%, Follow-up / Chronic Care / Telehealth ≈ 10% —
  New Patient runs roughly **2.5×** the low end.

The no-show rate is the clinic's core operational signal: a missed appointment is
capacity that was booked but wasted. A flat "12% no-show" reading hides that the
risk concentrates in one visit type: a patient who hasn't been seen before is
much likelier to skip the appointment than one coming back for routine care.
Bucket by `visit_type` and New Patient stands out — the natural target for a
reminder-call or deposit-on-booking intervention. The rate also climbs with
booking lead time, an independent axis (see
[`no-show-rises-with-lead-time.md`](no-show-rises-with-lead-time.md)), and pairs
with slot utilisation (see
[`provider-utilisation.md`](provider-utilisation.md)) for the full
booked-vs-wasted-capacity picture.

## How to find it

```sql
-- overall lifecycle mix
select status, count(*) * 1.0 / sum(count(*)) over () as share
from appointments
group by status;                     -- no_show ≈ 0.12

-- but no-show risk concentrates in New Patient visits
select visit_type,
       count(*)                                 as appts,
       avg((status = 'no_show')::int)            as no_show_rate  -- New Patient ≈ 0.20-0.23
from appointments
group by visit_type
order by no_show_rate desc;
```
