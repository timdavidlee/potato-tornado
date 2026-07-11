# Half of parcels are dimensional-weight-bound, but cost bills by actual weight

- **Signal:** for the low-density (bulky) parcels — a little over half the fleet —
  dimensional weight (`length_cm × width_cm × height_cm ÷ 5000`) exceeds actual
  `weight_kg`, so a real dim-weight carrier would rebill them higher. But
  `shipping_cost` is billed on `weight_kg` alone, so it systematically
  under-reflects *billable* weight on exactly that subset. The dim-bound flag is set
  by packing density (`weight_kg ÷ volume`), not by weight or `package_type`.
- **Tables:** `shipments.length_cm`, `shipments.width_cm`, `shipments.height_cm`,
  `shipments.weight_kg`, `shipments.shipping_cost`, `shipments.package_type`.
- **Magnitude:** ≈ **0.52** of parcels are dimensional-weight-bound (`dim_weight >
  weight_kg`). On that subset, billable weight (`max(weight_kg, dim_weight)`) runs
  ≈ **1.5×** actual on average and ≈ **2.2×** at the p90; across all parcels the
  billable/actual ratio averages ≈ **1.27×**. Being dim-bound is equivalent to
  packing density `< 200 kg/m³` (the cm→kg dim factor's break-even), and the median
  drawn density (≈ 195) sits just under it — so the split is ≈ 50/50 and roughly
  flat across `package_type` (≈ 0.51–0.54 each). `corr(dim_weight, shipping_cost)`
  ≈ **0.38**, *below* `corr(weight_kg, shipping_cost)` ≈ 0.44 — confirming size does
  **not** drive the stored cost. (Measured: `seed=7, scale=1.0`; already produced by
  today's generator.)

Real carriers bill the greater of actual and dimensional weight, so light-but-bulky
parcels don't ship cheap. This dataset deliberately keeps `shipping_cost` a clean
weight-based identity and leaves dimensional weight *derivable but unpriced* — which
plants a subset the student is meant to find: the ~half of parcels whose density
falls below the 200 kg/m³ break-even are "underbilled" relative to a dim-weight
tariff, and the uplift concentrates in the very lowest-density parcels (2×+ in the
tail). The teaching point is the dimensional-weight pricing lever itself: recompute
billable weight from the stored dimensions, find the dim-bound slice, and quantify
the revenue a weight-only tariff leaves on the table. It pairs with
`shipping-cost-right-skew.md` — that scenario reads cost off *actual* weight; this
one shows what a size-aware tariff would change and for whom.

## How to find it

```sql
-- billable weight = max(actual, dimensional); dim_weight = L*W*H / 5000
with b as (
  select weight_kg,
         (length_cm * width_cm * height_cm) / 5000.0            as dim_weight,
         package_type
  from shipments
)
select
  avg((dim_weight > weight_kg)::int)                            as dim_bound_frac,   -- ≈ 0.52
  avg(greatest(weight_kg, dim_weight) / weight_kg)             as billable_ratio,    -- ≈ 1.27
  avg(greatest(weight_kg, dim_weight) / weight_kg)
      filter (where dim_weight > weight_kg)                     as ratio_on_subset,   -- ≈ 1.51
  quantile_cont(greatest(weight_kg, dim_weight) / weight_kg, 0.9)
      filter (where dim_weight > weight_kg)                     as p90_on_subset      -- ≈ 2.15
from b;

-- the dim-bound split is ~50/50 within every package_type (density-, not size-driven)
select package_type,
       avg(((length_cm*width_cm*height_cm)/5000.0 > weight_kg)::int) as dim_bound_frac  -- ≈ 0.51–0.54
from shipments
group by package_type
order by package_type;
```
