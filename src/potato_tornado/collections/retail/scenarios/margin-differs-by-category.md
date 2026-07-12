# Gross margin differs sharply by category — and the highest-return category is the fattest

- **Signal:** gross margin rate varies sharply by product **category**, and it does
  *not* track the return-rate gradient: apparel — the highest-return category — also
  carries the **fattest** margin, while electronics runs the **thinnest** margin
  despite middling returns. Profitability and returns tell different stories per
  category, so "kill the category with all the returns" would cut the fattest-margin
  line.
- **Tables:** `products.category`, `products.cost`, `products.unit_price`
  (per-SKU margin = `(unit_price − cost) / unit_price`), cross-referenced with the
  per-category return rate from `order_items` ⋈ `returns` (see
  `return-rate-by-category.md`).
- **Magnitude — PLANTED.** Per-category mean margin, measured at seed 7, scale 0.5:
  **apparel ≈ 0.58 / home ≈ 0.44 / consumables ≈ 0.42 / electronics ≈ 0.28** (overall
  ≈ **0.46**) — a ~30-point apparel→electronics spread that runs *against* the return
  gradient at the extremes (apparel highest-return **and** highest-margin; electronics
  low-margin). The generator draws margin from a **per-category mean** with a small
  ≈0.05 within-category sd (`Normal(mean[category], 0.05)`, clamped to [0.05, 0.90]).

`cost` is `round(unit_price × (1 − margin), 2)` where `margin` is drawn from a
**per-category mean** (apparel/home/consumables fat-to-mid, electronics thin — the real
retail pattern: soft-goods markups are fat, consumer electronics is thin) with a small
≈0.05 within-category sd, clamped so `0 < cost < unit_price` for every SKU. That makes
the profit story diverge from the returns story the collection already teaches. The
teaching point: join margin and return rate by category and see they don't align —
apparel both returns the most (0.22) and earns the most per sale, so returns are a drag
on your *best* margin line, not a reason to cut it; electronics is thin-margin, so each
of its returns costs proportionally more. Profit health is `margin × (1 − return drag)`,
read per category, not the return rate alone.

## How to find it

```sql
-- margin by category vs return rate by category — they diverge
with margin as (
  select category,
         avg((unit_price - cost) / unit_price) as gross_margin
  from products
  group by category
),
ret as (
  select p.category,
         avg((r.order_item_id is not null)::int) as return_rate
  from order_items oi
  join products p using (product_id)
  left join returns r using (order_item_id)
  group by p.category
)
select m.category, m.gross_margin, r.return_rate
from margin m
join ret r using (category)
order by r.return_rate desc;
-- planted (seed 7, scale 0.5):  apparel      margin ~0.58  return ~0.22   (fattest AND highest-return)
--                               electronics  margin ~0.28  return ~0.10   (thinnest margin)
--                               home         margin ~0.44  return ~0.06
--                               consumables  margin ~0.42  return ~0.02
```
