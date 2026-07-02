# Return reasons differ by category

- **Signal:** *why* an item is returned is category-specific, not a uniform mix.
  Apparel returns are dominated by `changed_mind` + `too_small` (fit and
  second-thoughts); electronics returns are led by `defective` + `not_as_described`.
  Same funnel, different reason profile per category.
- **Tables:** `returns.reason`, `order_items.product_id`, `products.category`.
- **Magnitude:** in **apparel**, `changed_mind` + `too_small` ≈ **66%** of returns;
  in **electronics**, `defective` leads at ≈ **40%** (with `not_as_described` ≈ 30%)
  while `too_small` nearly vanishes. `damaged_in_transit` is small and roughly flat
  (~10%) across categories.

Each return's reason is drawn from a category-specific mix, so the reason
distribution shifts with the product. The teaching point is a grouped categorical
comparison: don't read the reason mix pooled — split it by category and the story
inverts (fit-driven for apparel, quality-driven for electronics). It pairs with
`return-rate-by-category.md`: apparel both returns *more* and returns for *different
reasons*.

## How to find it

```sql
-- reason mix by category: apparel skews changed_mind/too_small, electronics defective
select p.category, r.reason,
       count(*)::float / sum(count(*)) over (partition by p.category) as share
from returns r
join order_items oi using (order_item_id)
join products p using (product_id)
group by p.category, r.reason
order by p.category, share desc;
```
