# Fixed-dollar promos are regressive and invert revenue on the smallest baskets

- **Signal:** the promo discount is a **fixed dollar amount** drawn independently of
  basket size, so among promo orders its *effective* rate is steeply regressive — tiny
  on large baskets, huge on small ones — and on the very smallest baskets the discount
  exceeds the whole order, driving the derived net order total **negative**.
- **Tables:** `orders.promo_code`, `orders.discount_amount`, `order_charges.merchandise`,
  `order_charges.shipping_fee`, `order_charges.tax_amount` — the net total is the derived
  identity `merchandise + shipping_fee + tax_amount − discount_amount` (not stored).
- **Magnitude — ALREADY PRESENT.** Promo orders are ≈ **0.155** of all orders. Among
  them, the median effective discount rate (`discount_amount / merchandise`) collapses
  from ≈ **0.95** on baskets under \$25 to ≈ **0.08** on baskets ≥ \$100 (overall median
  ≈ 0.18) — a >10× spread purely from holding the dollar amount fixed. ≈ **21%** of
  under-\$25 promo baskets go net-negative; overall ≈ **0.4%** of *all* orders and ≈
  **2.6%** of *promo* orders have a negative net total (every net-negative order is a
  promo order). Only the \$15/\$20/\$25 tiers on tiny baskets can go negative — the
  \$5/\$10 tiers never do, because the shipping + tax floor already covers them.
  (Measured at `seed=7, scale=0.5`; ≈ 0.33% net-negative at `scale=1.0`.)

`discount_amount` is a flat dollar tier ({\$5, \$10, \$15, \$20, \$25}) drawn independently
of the basket — the header can't see its own lines without a build-order cycle, so the
discount can't be a share of merchandise. That independence is the whole point: a *fixed*
dollar credit is regressive toward small baskets in exactly the way a *percentage* coupon
would not be, and its effective rate explodes as the basket shrinks. The net order total is
deliberately **not** a stored column (like every other total here), so the signal only
appears once you derive it from `order_charges` minus `orders.discount_amount` — the same
join-and-derive muscle as `order-value-right-skew.md`. It is the mirror image of
`shipping-revenue-concentrates-in-small-baskets.md`: shipping is a fixed-dollar *charge*
whose effective rate is worst on small baskets, this is a fixed-dollar *credit* whose
effective rate is best (and, past 100%, revenue-destroying) on small baskets — both flat
per-order dollar amounts whose *rate* concentrates in the tiny left tail of the
right-skewed basket-value distribution. The teaching point: never read a fixed discount as
a flat give-back; band promo orders by merchandise and the effective subsidy — and a small
slice of net-negative orders — piles onto the smallest carts.

## How to find it

```sql
-- fixed-dollar promo is regressive: effective discount rate explodes on small baskets,
-- and a slice of tiny baskets goes net-negative (net total is DERIVED, not stored)
with promo as (
  select o.discount_amount,
         c.merchandise,
         o.discount_amount / nullif(c.merchandise, 0) as eff_disc_rate,
         c.merchandise + c.shipping_fee + c.tax_amount - o.discount_amount as net_total,
         case when c.merchandise < 25  then 'a_under_25'
              when c.merchandise < 50  then 'b_25_50'
              when c.merchandise < 100 then 'c_50_100'
              else 'd_100_plus' end as band
  from orders o
  join order_charges c using (order_id)
  where o.promo_code is not null            -- ~0.155 of all orders
)
select band,
       count(*)                               as n,
       median(eff_disc_rate)                  as med_eff_rate,  -- ~0.95 / 0.39 / 0.20 / 0.08
       avg((net_total < 0)::int)              as neg_share      -- ~0.21 / 0    / 0    / 0
from promo
group by band
order by band;
-- overall: ~2.6% of promo orders (~0.4% of all orders) have net_total < 0; every
-- net-negative order is a promo order, and only the $15/$20/$25 tiers reach it.
```
