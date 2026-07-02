# Provider utilisation varies across the roster

- **Signal:** providers publish open slots and only some fill; the booked fraction
  (utilisation) differs markedly from one provider to the next — some run nearly
  full, others sit half empty.
- **Tables:** `slots.is_booked`, `slots.provider_id`
- **Magnitude:** overall ≈ 68–70% of slots are booked, but per-provider utilisation
  spans ≈ 45% to ≈ 92%.

Utilisation is the clinic's capacity story: an empty slot is a provider-hour that
could have served a patient. Because each appointment books exactly one slot (no
double-booking), `booked / total` per provider is an exact utilisation rate — the
natural lead-in to "who has spare capacity?" and "where is demand concentrated?".

## How to find it

```sql
select
    provider_id,
    count(*)                        as total_slots,
    sum(is_booked::int)             as booked,
    avg(is_booked::int)             as utilisation   -- ranges ~0.45 .. ~0.92
from slots
group by provider_id
order by utilisation desc;
```
