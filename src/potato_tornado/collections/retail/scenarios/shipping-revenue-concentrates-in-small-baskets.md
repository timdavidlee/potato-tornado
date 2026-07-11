# Shipping-fee revenue concentrates in the smallest baskets

- **Signal:** shipping fees are steeply regressive and concentrated — the smallest
  ~1/8 of orders (`merchandise < $25`) pay a ~50%+ effective shipping rate and
  generate *over half* of all shipping revenue, while the ~70% of orders at/above the
  \$50 free-ship threshold pay nothing. "Most orders ship free" hides where the
  shipping money actually comes from.
- **Tables:** `order_charges.shipping_fee`, `order_charges.merchandise` (band the
  fee by the merchandise subtotal).
- **Magnitude:** free-ship threshold makes the fee a step function of basket value —
  \$0 at/above \$50 (≈ **0.70** of orders), \$4.99 in \$25–50 (≈ 0.18), \$7.99 under
  \$25 (≈ **0.13**). Only ≈ **0.30** of orders pay any fee. The `<$25` band is ≈
  **13%** of orders but ≈ **53%** of all shipping revenue, at a **median effective
  rate ≈ 0.53** (vs ≈ 0.14 for \$25–50, 0 above \$50).
  (Measured at `seed=7, scale=0.5`.)

The fee is a pure-deterministic function of the basket (`order_charges` builds after
the fan-out): free ≥ \$50, else a two-step tier. Read top-line, "≈70% of orders ship
free" sounds like shipping is a minor, evenly-spread cost. Band by merchandise and the
opposite is true: the fee is a concentrated, regressive line whose revenue piles onto
the very smallest orders — the tiny left tail of the right-skewed basket-value
distribution (see `order-value-right-skew.md`). The teaching point is not to read a
per-order fee as flat: group `order_charges` by a merchandise band and compute both the
*effective rate* (`shipping_fee / merchandise`) and each band's *share of total
shipping revenue* — a small, cheap slice of orders dominates both. This signal is
already present (no draws — it falls straight out of the threshold rule).

## How to find it

```sql
-- shipping revenue concentrates in the smallest baskets (regressive, deterministic)
with banded as (
  select case when merchandise < 25 then 'a_under_25'
              when merchandise < 50 then 'b_25_to_50'
              else 'c_50_plus' end            as band,
         merchandise, shipping_fee
  from order_charges
)
select band,
       count(*)::float / sum(count(*)) over ()             as order_share,    -- ~0.13 / ~0.18 / ~0.70
       avg(shipping_fee)                                   as avg_fee,        -- 7.99 / 4.99 / 0
       median(shipping_fee / nullif(merchandise, 0))       as med_ship_rate,  -- ~0.53 / ~0.14 / 0
       sum(shipping_fee) / sum(sum(shipping_fee)) over ()  as rev_share       -- ~0.53 / ~0.47 / 0
from banded
group by band
order by band;
-- the <$25 band is ~13% of orders but ~53% of all shipping revenue; ~70% of orders ship free
```
