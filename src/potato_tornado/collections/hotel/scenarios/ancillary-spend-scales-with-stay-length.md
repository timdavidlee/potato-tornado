# Ancillary spend scales with stay length

- **Signal:** the number of `service_orders` a stay accrues grows with its length — longer
  stays book more service-book entries (and thus more ancillary revenue), roughly linearly.
- **Tables:** `service_orders.stay_id`, `stays.actual_nights`, `service_orders.amount`
- **Magnitude:** order count ~ Poisson(**0.9 × actual_nights**), so ≈ **0.9 orders per
  night**; mean orders climbs ≈ 1 → 2 → 3 for 1 → 2 → 3-night stays, and the per-stay
  correlation between nights and order count is ≈ **0.67**.

Service-order rows are drawn per stay at a rate proportional to `actual_nights`, so ancillary
volume is a function of duration, not a flat per-stay constant. The teaching point is the
join-then-aggregate: to see the relationship a student must roll `service_orders` up to
`stay_id`, join back to `stays.actual_nights`, and regress or bucket — the signal is invisible
at the raw-row level. It also motivates a per-night normalisation (spend *per night* is roughly
flat; total spend is not).

## How to find it

```sql
-- orders per stay rise with stay length (≈ 0.9 per night)
select s.actual_nights,
       avg(o.orders) as mean_orders,           -- ≈ 0.9 × actual_nights
       count(*)      as stays
from stays s
left join (
  select stay_id, count(*) as orders
  from service_orders group by stay_id
) o using (stay_id)
group by s.actual_nights
order by s.actual_nights;

-- overall rate: total orders per total night ≈ 0.9
select count(*) * 1.0 / (select sum(actual_nights) from stays) as orders_per_night  -- ≈ 0.9
from service_orders;
```
