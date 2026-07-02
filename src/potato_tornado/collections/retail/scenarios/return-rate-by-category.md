# Return rate varies sharply by product category

- **Signal:** how often a line item comes back depends heavily on its product
  **category**. Apparel is returned many times more often than consumables — a
  covariate that dominates the overall return rate, so a single top-line number hides
  a strong category gradient.
- **Tables:** `returns.order_item_id`, `order_items.product_id`, `products.category`
  (a line is "returned" if its `order_item_id` appears in `returns`).
- **Magnitude:** ≈ **apparel 0.22 / electronics 0.10 / home 0.06 / consumables 0.02**
  (~**10×** apparel-vs-consumables), overall ≈ **0.12**.

Return propensity is a per-line Bernoulli whose probability is the product category's
`base_return_rate`, so the return decision is made per item and keyed only to
category. The teaching point is that the overall ~12% return rate is an average over
wildly different sub-populations: fixing "too many returns" means looking at apparel,
not the whole catalog. It's the setup for a "where are returns coming from?" question
— the answer is one or two categories, not a flat rate.

## How to find it

```sql
-- return rate climbs steeply by category (consumables ~0.02 → apparel ~0.22)
select p.category,
       avg((r.order_item_id is not null)::int) as return_rate,
       count(*)                                as lines
from order_items oi
join products p using (product_id)
left join returns r using (order_item_id)
group by p.category
order by return_rate;
```
