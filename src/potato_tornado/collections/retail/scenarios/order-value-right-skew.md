# Order value is right-skewed and basket-size driven

- **Signal:** an order's total value — the `sum(line_total)` over its lines — is
  right-skewed: most baskets are modest, a heavy tail comes from large baskets and
  high-price items. Basket value is a **derived aggregate**, not a stored header
  column, so surfacing it is a join-and-group-by.
- **Tables:** `order_items.line_total` aggregated to `order_id`;
  `orders.item_count` (the basket size).
- **Magnitude:** basket value median ≈ **\$80**, p95 ≈ **\$290**, mean ≈ **\$107**
  (mean above median — the skew). Baskets hold `1 + Poisson(1.5)` lines (mean ≈ 2.5,
  tail to ~8), and `unit_price` is itself lognormal (median ≈ \$23), so both the line
  count and the per-line price feed the tail.

The header deliberately stores no `order_total` — computing it from the lines is the
point, and it sidesteps a redundant column that could drift from the fan-out. The
teaching point is header/line aggregation: join `orders` to `order_items`, group by
`order_id`, sum the line totals, and read the distribution as a right-skewed one
(report a median and a p95, not a mean). Decompose the tail and it's the multi-item
and premium-category baskets.

## How to find it

```sql
-- basket value is right-skewed: p95 several× the median, mean above median
with basket as (
  select order_id, sum(line_total) as value
  from order_items group by order_id
)
select quantile_cont(value, 0.5)  as p50,   -- ≈ 80
       quantile_cont(value, 0.95) as p95,   -- ≈ 290
       avg(value)                 as mean_  -- ≈ 107, above p50
from basket;
```
