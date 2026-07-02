# Visit-type mix depends on the provider's specialty

- **Signal:** what happens in the room tracks who the provider is — a paediatrician's
  book skews toward new-patient and annual-physical visits, a dermatologist's or
  orthopaedist's toward minor procedures, while a family-medicine provider carries the
  broad routine mix. The clinic-wide visit-type marginal is the average of these
  distinct per-specialty profiles.
- **Tables:** `appointments.visit_type`, `providers.specialty`
  (join `appointments.provider_id → providers.provider_id`)
- **Magnitude:** Minor Procedure is ≈ 9–10% of visits clinic-wide but ≈ 21–27% for
  Dermatology/Orthopedics and ≈ 0% for Pediatrics; New Patient is ≈ 13% clinic-wide but
  ≈ 22% for Pediatrics; Chronic Care is ≈ 18–20% clinic-wide but ≈ 32–43% for Internal
  Medicine/Cardiology. Each specialty's mix is visibly skewed from the overall, while the
  clinic-wide marginal stays near the base booking weights (Follow-up ≈ 0.32 / Chronic Care
  ≈ 0.18 / Annual Physical ≈ 0.16 / New Patient ≈ 0.13 / Minor Procedure ≈ 0.09 / Telehealth
  ≈ 0.10 — within a couple points of the `VISIT_TYPES` weights, drifting a little with the
  randomly assigned specialty roster).

A "clinic" is really several different practices sharing a front desk, and lumping their
visit mix together hides that. Surfacing the per-specialty profile is the setup for
capacity and templating questions that the clinic-wide average can't answer — e.g. a
dermatology slot should be sized for procedures, not follow-ups. The generator draws
`visit_type` from the booked provider's specialty profile (`SPECIALTY_VISIT_MIX` in
`constants.py`, applied per specialty group in `tables/appointments.py`), so each specialty
shows its own mix while the appointment-weighted average stays near the base booking
weights. Because appointments book real slots, the slot's `provider_id` — and thus its
specialty — drives the draw.

## How to find it

```sql
select
    p.specialty,
    a.visit_type,
    count(*)                                                        as appts,
    count(*) * 1.0 / sum(count(*)) over (partition by p.specialty)  as share_within_specialty
from appointments a
join providers p on p.provider_id = a.provider_id
group by p.specialty, a.visit_type
order by p.specialty, share_within_specialty desc;
-- Dermatology/Orthopedics: Minor Procedure share ~0.20-0.25 (vs ~0.08 overall)
-- Pediatrics: New Patient share ~0.20+ (vs ~0.12 overall)
```
