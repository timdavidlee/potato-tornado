# Provider utilisation concentrates by specialty

- **Signal:** providers publish open slots and only some fill. The booked fraction
  (utilisation) is not random noise across the roster — it tracks the provider's
  **specialty**: demand-heavy specialties (Dermatology, Cardiology) run near-full,
  while others (Pediatrics, Family Medicine) sit with visible spare capacity.
  Clinicians in the same specialty differ only by a small jitter.
- **Tables:** `slots.is_booked`, `slots.provider_id`, `providers.specialty`
  (join `slots.provider_id → providers.provider_id`)
- **Magnitude:** overall ≈ 68–70% of slots booked, but per-specialty utilisation
  spans ≈ 0.88 (Dermatology) / 0.82 (Cardiology) / 0.74 (Orthopedics) / 0.64
  (Internal Medicine) / 0.56 (Family Medicine) / 0.48 (Pediatrics), ±~4% per
  provider. Demand-heavy specialties run ~1.8× the utilisation of the lightest.

Utilisation is the clinic's capacity story, and the teaching point is *where* the
spare capacity lives. A student looking at the clinic-wide ~69% sees a single
occupancy number; grouping by provider shows a spread, but grouping by specialty
shows the spread is *structured* — it's a demand story, not luck. Because each
appointment books exactly one slot (no double-booking), `booked / total` per
provider is an exact utilisation rate, and rolling it up to specialty answers "who
has room to take more patients?" (the light specialties) and "where is demand
outstripping supply?" (the full ones). It pairs with `visit-mix-by-specialty.md`:
the clinic is several practices sharing a front desk, and they fill at different
rates.

## How to find it

```sql
-- utilisation by specialty: demand-heavy specialties run near-full, others have slack
select
    p.specialty,
    count(*)              as total_slots,
    avg(s.is_booked::int) as utilisation      -- ~0.88 Dermatology .. ~0.48 Pediatrics
from slots s
join providers p on p.provider_id = s.provider_id
group by p.specialty
order by utilisation desc;

-- clinic-wide occupancy hides it
select avg(is_booked::int) as overall_utilisation from slots;   -- ≈ 0.68-0.70
```
