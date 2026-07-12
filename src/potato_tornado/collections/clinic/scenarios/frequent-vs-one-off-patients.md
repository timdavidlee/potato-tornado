# A minority of patients account for a majority of visits

- **Signal:** patients do not book uniformly — a core of frequent, returning patients
  (chronic-care and annual-follow-up types) rebook far more often than the long tail of
  one-off patients, so appointment volume concentrates in a small share of the panel.
- **Tables:** `appointments.patient_id` (optionally joined to `patients`)
- **Magnitude:** the top 10% of patients by visit count account for ≈ 33–40% of all
  appointments, and the top 20% for ≈ 51–57%; a Pareto-style skew (a uniform draw would give
  the top decile only ≈ 15–17%). The long tail is real: ≈ 5–7% of registered patients never
  book at all. Total appointment volume is unchanged — only the *distribution of bookings
  across patients* is reshaped. (These ranges are sharper than the bare lognormal shape
  because the clinical booking tilt in `high-risk-patients-drive-visits.md` raises the weight
  of the already-frequent core — the two signals compound.)

"How many patients do we have?" and "how many visits do we have?" are different questions,
and the gap between them is the retention story. A skewed booking distribution is the setup
for cohort and lifetime-value reasoning — a clinic keeps its lights on with the returning
core, not the one-off visitors. `appointments` draws its patient with a per-patient lognormal
booking propensity (`_draw_patients`, σ ≈ 0.8), so a minority rebook heavily while a long tail
books rarely or never; a clinical booking tilt then multiplies that weight up for the chronic
/ high-`risk_score` minority (see `high-risk-patients-drive-visits.md`), compounding the
concentration. The draw runs on an independent `child("patient_bookings")` stream, so
nothing else in the collection shifts — patient identity only passes through to `visits` and
`invoices`.

## How to find it

```sql
with per_patient as (
    select patient_id, count(*) as visits
    from appointments
    group by patient_id
),
ranked as (
    select
        visits,
        cume_dist() over (order by visits desc) as patient_pctile
    from per_patient
)
select
    sum(case when patient_pctile <= 0.10 then visits else 0 end) * 1.0 / sum(visits)  as top10_share, -- ~0.33-0.40
    sum(case when patient_pctile <= 0.20 then visits else 0 end) * 1.0 / sum(visits)  as top20_share  -- ~0.51-0.57
from ranked;
```
