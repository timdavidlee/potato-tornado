# A chronic, high-risk patient minority drives a disproportionate share of visits

- **Signal:** appointment volume concentrates in the clinically sickest patients — the
  chronic / high-`risk_score` minority (≈ 22% of the panel) books far more often than
  everyone else, so it accounts for a share of appointments well above its share of
  patients. Booking frequency is not spread evenly across the panel; it tracks clinical
  burden.
- **Tables:** `patients.chronic_flag`, `patients.risk_score`, `appointments.patient_id`
  (join `appointments.patient_id → patients.patient_id`)
- **Magnitude:** *target, to be planted.* Chronic patients are ≈ 22% of the panel but
  book ≈ **38–42%** of appointments (a per-capita rate ≈ **2×** a non-chronic patient),
  and the continuous `risk_score` correlates **positively** with a patient's visit count
  (target corr ≈ **0.30+**; equivalently the top `risk_score` quartile takes ≈ 40% of
  appointments vs ≈ 25% uniform). Total appointment volume is unchanged — only *which*
  patients fill the slots is reshaped.

Today this signal is **not planted**. `patients.chronic_flag` (≈ 0.22) and
`patients.risk_score` are drawn flat and independent of booking propensity (see the
"Patient clinical attributes carry no planted signal" note in `realism-guidance.md` and
item 3 in `TODO.md`): measured at seed 7 / scale 0.5 the chronic minority takes only
≈ 27% of appointments (≈ its population share, the rest sampling noise) and
`corr(risk_score, appts) ≈ 0.04` — i.e. no clinical driver. To plant it, tilt the
per-patient lognormal booking propensity in `_draw_patients` (`tables/appointments.py`)
upward for `chronic_flag = true` / high `risk_score`, so clinical burden raises rebooking
frequency. It must **compose with, not replace,** the existing heavy-tailed propensity
(the Pareto booking shape in `frequent-vs-one-off-patients.md`) and preserve total
appointment volume, and it must not disturb referential integrity or the
one-appointment-per-slot invariant (patient identity only selects the booker; it never
changes slot count or the completed → visit → invoice chain). Reconcile the
`frequent-vs-one-off-patients.md` top-decile magnitude in the same change, since adding a
clinical tilt sharpens the concentration.

The teaching point is the **population-health / risk-stratification** story that
`frequent-vs-one-off-patients.md` sets up but stops short of: that doc shows appointment
volume is Pareto-skewed across the panel *without saying who the heavy bookers are*; this
one names the driver — the frequent bookers are disproportionately the chronically ill.
That is the difference between "a minority books a lot" (a distribution shape) and "the
sickest patients are our high utilizers" (an actionable segment). Grouping visit volume by
`chronic_flag` / `risk_score` band is the setup for a care-management question: which
patients should a high-utilizer or complex-care program enrol, and what visit demand would
managing them better take off the schedule?

## How to find it

```sql
-- Chronic patients are a ~22% minority but book a disproportionate share of appointments.
select
    p.chronic_flag,
    count(distinct p.patient_id)                                          as patients,
    count(a.appointment_id)                                              as appts,
    count(a.appointment_id) * 1.0 / sum(count(a.appointment_id)) over ()  as appt_share
from patients p
left join appointments a on a.patient_id = p.patient_id
group by p.chronic_flag;
-- target once planted: chronic=true ≈ 22% of patients but ≈ 0.40 appt_share
-- (today it sits at ≈ its population share, ≈ 0.22-0.27 — no planted signal)

-- Per-capita: a chronic patient books ~2x as often as a non-chronic one.
select
    p.chronic_flag,
    count(a.appointment_id) * 1.0 / count(distinct p.patient_id) as appts_per_patient
from patients p
left join appointments a on a.patient_id = p.patient_id
group by p.chronic_flag;
-- target: chronic ≈ 2x non-chronic

-- Continuous companion: risk_score rises with a patient's visit count.
with per_patient as (
    select p.patient_id, p.risk_score, count(a.appointment_id) as appts
    from patients p
    left join appointments a on a.patient_id = p.patient_id
    group by p.patient_id, p.risk_score
)
select corr(risk_score, appts) as risk_visit_corr from per_patient;
-- target ≈ 0.30+  (today ≈ 0.04, i.e. no signal)
```
