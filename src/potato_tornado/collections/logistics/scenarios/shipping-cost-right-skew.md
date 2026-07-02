# Shipping cost is right-skewed, with a weight-driven tail

- **Signal:** `shipping_cost` is right-skewed — most parcels are cheap, a thin tail
  is expensive — and the tail is driven by parcel **weight**. Cost follows an exact
  arithmetic identity (base + weight × per-kg + zone fee, scaled by the service
  multiplier), so the heavy long tail of `weight_kg` shows through as the cost tail.
- **Tables:** `shipments.shipping_cost`, `shipments.weight_kg`, `shipments.dest_zone`,
  `shipments.service_level`, `shipments.carrier_id`.
- **Magnitude:** median ≈ **\$12**, p95 ≈ **\$27**, max past **\$80**. Weight is
  right-skewed (lognormal, median ≈ 2 kg clamped to [0.1, 50]); `corr(weight_kg,
  shipping_cost)` ≈ **0.44** — weight is one of three cost drivers (alongside zone
  and the service multiplier), so the correlation is moderate but the extreme costs
  are the heavy parcels.

Skew comes from the `weight_kg` draw, not a second lognormal on cost — the cost is a
deterministic function of weight, zone, carrier rates and service tier. The teaching
point is twofold: an average shipping cost is misleading (report a median and a
p95), and the cost tail is explainable — decompose it and the heaviest parcels sit
at the top. It also sets up a clean check that the stored `shipping_cost` matches the
identity exactly (a realism invariant).

## How to find it

```sql
-- right-skew: mean sits above the median, with a long upper tail
select quantile_cont(shipping_cost, 0.5)  as p50,   -- ≈ 12
       quantile_cont(shipping_cost, 0.95) as p95,   -- ≈ 27
       max(shipping_cost)                  as max_,  -- ≈ 84
       corr(weight_kg, shipping_cost)      as r      -- ≈ 0.44
from shipments;
```
