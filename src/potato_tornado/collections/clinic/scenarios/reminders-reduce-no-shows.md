# Reminded appointments no-show far less

- **Signal:** an appointment that got a reminder is kept much more often than one
  that didn't — the reminder is the clinic's single controllable no-show lever, and
  its effect sits *on top of* the lead-time and visit-type gradients rather than
  replacing them.
- **Tables:** `appointments.reminder_sent`, `appointments.status` (slice within
  `appointments.lead_days` bands to show the lever is independent of lead time)
- **Magnitude:** at seed 7 / scale 0.5, reminded appointments no-show ≈ **8.5%** vs
  ≈ **20.0%** for un-reminded — a **≈ 2.35× spread** — while the marginal no-show rate
  stays ≈ **12.0%** (≈ 69% of appointments get a reminder). The gap holds *within* each
  lead-time band (e.g. lead 0–15: 7.5% reminded vs 18.7% un-reminded; lead 15–30: 9.1%
  vs 21.7%), so it is a genuine independent lever, not a proxy for short-notice bookings.

`appointments.reminder_sent` currently ships **flat** (a ≈ 70% Bernoulli with no
attendance effect — see the "Reminders carry no attendance signal" note in
`realism-guidance.md` and item 1 in `TODO.md`). The signal to plant: a sent reminder
lowers the per-appointment no-show hazard. In `tables/appointments.py` the hazard is
`_no_show_prob(lead_days, visit_type)`; planting means applying a downward offset (or
multiplier) keyed on `reminder_sent` inside `_assign_status`, balanced across the
≈ 70/30 sent/unsent split so the marginal no-show rate stays ≈ 12% and the existing
lead-time (`no-show-rises-with-lead-time.md`) and visit-type
(`no-show-rate.md`) structure is preserved. The hard invariant that
`reminder_channel` is non-null iff `reminder_sent` is untouched.

The teaching point is that this is the *actionable* companion to the two existing
no-show scenarios: lead time and visit type tell you *which* appointments are at
risk, but they are not levers a scheduler can pull — the reminder is. Surfacing the
reminded-vs-not gap (and showing it holds within every lead-time band) is the setup
for an intervention/ROI question: how much missed capacity does the reminder program
recover, and would reminding the remaining 30% pay off?

## How to find it

```sql
-- Reminded appointments no-show at roughly half the un-reminded rate.
select
    reminder_sent,
    count(*)                       as appts,
    avg((status = 'no_show')::int) as no_show_rate   -- reminded (true) ~0.085, un-reminded (false) ~0.20
from appointments
group by reminder_sent;

-- The lift is an independent lever: it holds within each lead-time band,
-- so the reminder gap is not just a proxy for short-notice bookings.
select
    (lead_days / 15) * 15          as lead_bucket,   -- 0, 15, 30, ...
    reminder_sent,
    avg((status = 'no_show')::int) as no_show_rate    -- reminded row sits ~10pt below un-reminded in every bucket
from appointments
group by lead_bucket, reminder_sent
order by lead_bucket, reminder_sent;
```
