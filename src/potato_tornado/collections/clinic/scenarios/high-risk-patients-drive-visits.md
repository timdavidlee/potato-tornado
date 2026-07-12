# A chronic, high-risk patient minority drives a disproportionate share of visits

- **Signal:** appointment volume concentrates in the clinically sickest patients — the
  chronic / high-`risk_score` minority (≈ 22% of the panel) books far more often than
  everyone else, so it accounts for a share of appointments well above its share of
  patients. Booking frequency is not spread evenly across the panel; it tracks clinical
  burden.
- **Tables:** `patients.chronic_flag`, `patients.risk_score`, `appointments.patient_id`
  (join `appointments.patient_id → patients.patient_id`)
- **Magnitude:** chronic patients are ≈ 22% of the panel but book ≈ **41%** of
  appointments (a per-capita rate ≈ **2.4×** a non-chronic patient), and the continuous
  `risk_score` correlates **positively** with a patient's visit count (corr ≈ **0.38** at
  seed 7 / scale 0.5; equivalently the top `risk_score` quartile takes ≈ **45–50%** of
  appointments vs ≈ 25% uniform). Both effects are seed-sensitive on the small panel —
  across seeds the chronic share runs ≈ 33–41% (per-capita ≈ 1.4–2.4×) and the correlation
  ≈ 0.23–0.40. Total appointment volume is unchanged — only *which* patients fill the slots
  is reshaped.

This signal is planted in `_draw_patients` (`tables/appointments.py`): a log-linear
clinical multiplier (`exp(0.40 · chronic_flag + 2.5 · (risk_score − 0.35))`) tilts the
per-patient booking weight toward the chronic / high-`risk_score` minority, **composing
with, not replacing,** the existing heavy-tailed lognormal propensity (the Pareto booking
shape in `frequent-vs-one-off-patients.md`). The multiplier reads deterministic patient
columns — it adds no random draw and reorders none — so it preserves total appointment
volume, referential integrity, and the one-appointment-per-slot invariant (patient identity
only selects the booker; it never changes slot count or the completed → visit → invoice
chain). Because the tilt raises the weight of the already-frequent core, it also sharpens
the frequent-vs-one-off concentration (see that doc's reconciled top-decile magnitude).
Before planting, `chronic_flag` / `risk_score` were flat and independent of booking
propensity — the chronic minority took only ≈ 22–27% of appointments (≈ its population
share) and `corr(risk_score, appts) ≈ 0.04`.

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
-- planted: chronic=true ≈ 22% of patients but ≈ 0.41 appt_share (seed 7 / scale 0.5)

-- Per-capita: a chronic patient books ~2x as often as a non-chronic one.
select
    p.chronic_flag,
    count(a.appointment_id) * 1.0 / count(distinct p.patient_id) as appts_per_patient
from patients p
left join appointments a on a.patient_id = p.patient_id
group by p.chronic_flag;
-- planted: chronic ≈ 2.4x non-chronic (seed 7 / scale 0.5)

-- Continuous companion: risk_score rises with a patient's visit count.
with per_patient as (
    select p.patient_id, p.risk_score, count(a.appointment_id) as appts
    from patients p
    left join appointments a on a.patient_id = p.patient_id
    group by p.patient_id, p.risk_score
)
select corr(risk_score, appts) as risk_visit_corr from per_patient;
-- planted ≈ 0.38 (seed 7 / scale 0.5); before planting ≈ 0.04
```
