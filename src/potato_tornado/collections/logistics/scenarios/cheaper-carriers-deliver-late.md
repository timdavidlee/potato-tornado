# Cheaper carriers deliver late more often — a price/reliability tradeoff

- **Signal:** on-time delivery is not uniform across carriers — it climbs with the
  carrier's static `reliability`, and because the carrier catalog couples price and
  reliability (dearer carriers are more reliable), the *cheapest* lane is also the
  *least* on-time. Join delivery outcomes back to the carrier and a clean cost/quality
  tradeoff appears that the ~86% top-line on-time rate hides.
- **Tables:** `carriers.reliability`, `carriers.base_rate`, `carriers.per_kg_rate`,
  `shipments.carrier_id`, `shipments.shipping_cost`, `deliveries.days_late`,
  `deliveries.status` (join `deliveries → shipments → carriers` on `shipment_id` /
  `carrier_id`).
- **Magnitude:** overall on-time ≈ **0.86**, but by carrier it rises **monotonically**
  from ≈ **0.80** on the cheapest carrier (Coyote Ground, `reliability` 0.85, mean
  `shipping_cost` ≈ \$12) to ≈ **0.91** on the priciest (Summit Courier, `reliability`
  0.97, mean `shipping_cost` ≈ \$16) — a ≈ **2.3×** spread in the *miss* rate (≈ 0.20 vs
  ≈ 0.087). Across the 5-carrier catalog `corr(base_rate, reliability)` ≈ **0.98** (and
  `corr(per_kg_rate, reliability)` ≈ 0.93), so price and reliability move together.
  (Measured: `seed=7` and `seed=42`, `scale=1.0`; already produced by today's
  generator.)

On-time propensity is `reliability + a small bonus − a per-zone penalty`, so a
shipment's on-time chance inherits its carrier's static `reliability` prior. Carriers
are assigned uniformly and the zone/weight/service mix is the same for each, so the
per-carrier on-time ranking is driven purely by `reliability` — and `reliability` is
tuned to rise with the carrier's rates in `constants.py`. The teaching point is a
cross-table "you get what you pay for": `reliability` is a static dimension attribute
that looks inert until you join outcomes back to it, at which point the cheapest carrier
is revealed as the one that misses the SLA most. This is distinct from
`on-time-degrades-with-zone.md` — there the covariate is per-shipment *distance* set at
dispatch; here it is the carrier's own reliability, and it is coupled to what the carrier
costs. The two levers stack: a cheap carrier to a far zone is the worst-case lane.

## How to find it

```sql
-- on-time rate climbs with carrier reliability (and with price):
-- the cheapest carrier misses the SLA ~2.3x more often than the priciest.
select c.carrier_name,
       c.reliability,
       avg(s.shipping_cost)          as avg_cost,      -- Coyote ≈ 12 … Summit ≈ 16
       avg((d.days_late <= 0)::int)  as on_time_rate,  -- Coyote ≈ 0.80 … Summit ≈ 0.91
       count(*)                      as delivered
from deliveries d
join shipments s using (shipment_id)
join carriers  c using (carrier_id)
where d.status = 'delivered'
group by c.carrier_name, c.reliability
order by c.reliability;   -- on_time_rate and avg_cost both rise monotonically

-- the catalog itself couples price and reliability (you get what you pay for)
select corr(base_rate, reliability)   as r_base,   -- ≈ 0.98 across the 5 carriers
       corr(per_kg_rate, reliability) as r_perkg   -- ≈ 0.93
from carriers;
```
