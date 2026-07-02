# On-time delivery degrades with shipping zone

- **Signal:** the farther the destination (`dest_zone`, a 1–8 distance proxy), the
  lower the on-time rate. On-time (`days_late <= 0`) falls steadily from the near
  zones to the far ones — a covariate-driven SLA degradation, not a flat miss rate.
- **Tables:** `shipments.dest_zone`, `shipments.promised_date`,
  `deliveries.days_late`, `deliveries.status` (join on `shipment_id`).
- **Magnitude:** on-time ≈ **0.96 at zone 1** declining to ≈ **0.75 at zone 8**
  (overall ≈ **0.86**) — roughly a 5× jump in the *miss* rate across the ladder
  (~0.04 → ~0.25). Measured on `status = 'delivered'` rows only.

On-time propensity blends carrier `reliability` with a linear per-zone penalty: a
small bonus lifts near-zone parcels and a zone slope drags far ones down, so the
promised date is kept less often the farther a parcel travels. The teaching point
is that a single top-line on-time number (~86%) hides a strong distance gradient —
the SLA is comfortably met close to home and routinely missed cross-country. This
is distinct from clinic's lead-time gradient: here the covariate is *distance*, set
at dispatch, not elapsed booking time.

## How to find it

```sql
-- on-time rate declines monotonically with distance zone
select s.dest_zone,
       avg((d.days_late <= 0)::int) as on_time_rate,   -- zone 1 ≈ 0.96 … zone 8 ≈ 0.75
       count(*)                     as delivered
from deliveries d
join shipments s using (shipment_id)
where d.status = 'delivered'
group by s.dest_zone
order by s.dest_zone;
```
