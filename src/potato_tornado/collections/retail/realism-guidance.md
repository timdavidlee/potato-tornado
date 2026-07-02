# Realism guidance — retail

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** `orders.customer_id ∈ customers`;
  `order_items.order_id ∈ orders` and `order_items.product_id ∈ products`;
  `returns.order_item_id ∈ order_items` and `returns.order_id ∈ orders`.
- **One return per line, at most.** `order_item_id` is unique in `returns` (a line is returned
  zero or one times, never split).
- **Fan-out consistency.** `orders.item_count` equals the number of `order_items` rows for that
  order (`sum(item_count) == order_items.height`).
- **Arithmetic identities.** `line_total = round(quantity × unit_price, 2)`;
  `refund_amount ≤ line_total`.
- **Temporal ordering.** `order_date ≥ customers.signup_date` for that customer;
  `return_date ≥ order_date`; both `order_date` and `return_date` fall within the run window.
- **Non-negativity / bounds.** `quantity ∈ {1, 2, 3}`, `unit_price ∈ [1, 500]`,
  `refund_amount > 0`, `item_count ≥ 1`.
- **Catalogs are fixed.** `products.category ∈ CATEGORIES`; `returns.reason ∈ RETURN_REASONS`;
  `orders.channel ∈ {web, mobile, marketplace}`; `orders.status ∈ {delivered, shipped,
  cancelled}`; `customers.segment ∈ {new, returning, vip}`.

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `customers` = 3000, `products` = 500, `orders` = 12000,
  `order_items` ≈ 2.5 × orders (≈ 30k, variable), `returns` ≈ 12% of `order_items` (≈ 3.5k).
- **unit_price.** Lognormal (σ ≈ 0.7) with a per-category median (apparel \$22 / electronics
  \$55 / home \$26 / consumables \$8), clamped to [\$1, \$500]. Overall median ≈ **\$23**, a
  long premium tail.
- **Category mix.** apparel 0.34 / home 0.26 / consumables 0.22 / electronics 0.18.
- **item_count per order.** `1 + Poisson(1.5)` → mostly 1–3 items, tail to ~8, mean ≈ **2.5**.
- **quantity per line.** 1 (0.80) / 2 (0.15) / 3 (0.05).
- **Basket value.** `sum(line_total)` per order is right-skewed: median ≈ **\$80**, p95 ≈
  **\$290**, mean ≈ \$107. Derived, not stored. See `scenarios/order-value-right-skew.md`.
- **channel mix.** web 0.50 / mobile 0.40 / marketplace 0.10.
- **order status.** delivered 0.90 / shipped 0.05 / cancelled 0.05.
- **Return rate (category-driven).** apparel ≈ 0.22 / electronics ≈ 0.10 / home ≈ 0.06 /
  consumables ≈ 0.02 → overall ≈ **0.12**. See `scenarios/return-rate-by-category.md`.
- **Return reason mix (category-specific).** apparel skews `changed_mind` + `too_small`
  (~66%); electronics skews `defective` (~40%) + `not_as_described`; `damaged_in_transit` is
  small and roughly flat (~10%) across categories. See
  `scenarios/return-reasons-differ-by-category.md`.
- **refund_amount.** Full line refund 0.90; else a restocking-fee partial 0.6–0.9× the line
  total. `restocked` depends on reason — fit/mind-change usually restock (~0.9),
  defective/damaged rarely do (~0.05).
- **return_date.** order date + 5–30 days, clipped to stay inside the window.

## Deliberate simplifications (intended — do not "fix")

- **No stored basket total.** `orders` has no `order_total`; basket value is deliberately a
  `sum(order_items.line_total)` aggregate (the join-and-group-by teaching point), so nothing
  can drift from the fan-out. `item_count` *is* stored and pinned to the realized line count.
- **No price history.** A line's `unit_price` is a snapshot of the current product price — no
  promotions, discounts, coupons, or per-order/per-customer pricing. The same product on two
  orders shows the same price.
- **One return per line, whole-line only** — no partial-quantity returns (you can't return 1
  of a quantity-3 line) and no re-returns.
- **Order value excludes tax and shipping.** There is no shipping/fees/tax table; basket value
  is purely merchandise.
- **No inventory or stock model.** Any product can appear on any order in any quantity; there
  are no stockouts, and `restocked` doesn't feed back into available inventory.
- **Return propensity and reason depend only on category** — not on price, customer segment,
  channel, quantity, or season. A real store would couple returns to fit/size data and customer
  history; here category is the sole covariate (the planted signal).
- **`segment` and `channel` carry no signal** — they're drawn independently of order value,
  return behavior, and each other; they exist for slicing practice, not a planted
  segment/channel scenario (natural future additions).

## How to review

```sql
-- fan-out consistency: header item_count matches the realized line count (expect equal)
select (select sum(item_count) from orders) as header_lines,
       (select count(*) from order_items)   as actual_lines;

-- line_total identity and refund bound (expect 0 each)
select count(*) filter (where round(quantity * unit_price, 2) <> line_total) as bad_line_total
from order_items;
select count(*) as bad_refund
from returns r join order_items oi using (order_item_id)
where r.refund_amount > oi.line_total;

-- one return per line (expect 0 duplicates)
select count(*) - count(distinct order_item_id) as dup_returns from returns;

-- return rate climbs by category (~0.02 → ~0.22)
select p.category, avg((r.order_item_id is not null)::int) as return_rate
from order_items oi
join products p using (product_id)
left join returns r using (order_item_id)
group by p.category order by return_rate;
```
