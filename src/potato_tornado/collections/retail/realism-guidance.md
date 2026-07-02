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
  cancelled}`; `customers.segment ∈ {new, returning, vip}`;
  `customers.acquisition_channel ∈ {organic, paid_search, social, referral, email}`;
  `orders.payment_method ∈ {card, paypal, gift_card, bnpl}`;
  `returns.refund_method ∈ {original_payment, store_credit, exchange}`;
  `products.brand ∈` the row category's brand catalog.
- **Non-negativity / bounds (added fields).** `products.weight_kg ∈ [0.05, 30]`.

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `customers` = 3000, `products` = 500, `orders` = 12000,
  `order_items` ≈ 2.5 × orders (≈ 30k, variable), `returns` ≈ 12% of `order_items` (≈ 3.5k).
- **unit_price.** Lognormal (σ ≈ 0.7) with a per-category median (apparel \$22 / electronics
  \$55 / home \$26 / consumables \$8), clamped to [\$1, \$500]. Overall median ≈ **\$23**, a
  long premium tail. Cents are continuous (not charm-priced) and prices don't cluster on
  round numbers; ~0.96 of SKUs carry a distinct price (no lattice).
- **product_name.** `adjective × per-category qualifier × noun` (12 × 6 × 6 ≈ 432 combos per
  category), so duplicate names are rare — ≈ **0.95** of the 500 SKUs carry a distinct name. A
  synthetic label for joins, not a real SKU master.
- **Category mix.** apparel 0.34 / home 0.26 / consumables 0.22 / electronics 0.18.
- **item_count per order.** `1 + Poisson(1.5)` → mostly 1–3 items, tail to ~8, mean ≈ **2.5**.
- **quantity per line.** 1 (0.80) / 2 (0.15) / 3 (0.05).
- **Basket value.** `sum(line_total)` per order is right-skewed: median ≈ **\$80**, p95 ≈
  **\$290**, mean ≈ \$107. Derived, not stored. See `scenarios/order-value-right-skew.md`.
- **channel mix.** web 0.50 / mobile 0.40 / marketplace 0.10.
- **order status.** delivered 0.90 / shipped 0.05 / cancelled 0.05.
- **order_date (seasonal).** Sampled across the `[start, end)` window with a repeating
  within-year retail cycle — a Q4 holiday peak (Nov ×1.4 / Dec ×1.55) and a Feb trough
  (×0.80), ~1.9x peak-to-trough — so Nov+Dec ≈ **0.31** of a year's orders (vs 0.17 for a flat
  calendar) and the peak recurs each year. On top of the cycle, order volume *grows* across
  the window as the customer base accumulates (each customer orders only on/after signup); the
  monotonic year-over-year rise is a plausible growth trend, not seasonality.
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
- **brand (`products`).** Uniform over the row category's 5-brand house catalog — so brand
  sits *inside* the category, and a brand-level sales/return slice just re-expresses the
  category gradient (no independent brand signal).
- **weight_kg (`products`).** Lognormal (σ ≈ 0.5) with a per-category median (apparel 0.45 /
  electronics 1.1 / home 1.6 / consumables 0.5 kg), clamped to [0.05, 30]. A shipping-cost
  covariate, not yet coupled to `damaged_in_transit` returns.
- **acquisition_channel (`customers`).** organic 0.30 / paid_search 0.25 / social 0.20 /
  email 0.13 / referral 0.12. Independent of `segment` and of order/return behaviour.
- **marketing_opt_in (`customers`).** Boolean, `True` ≈ 0.60. Independent of everything else.
- **payment_method (`orders`).** card 0.55 / paypal 0.22 / bnpl 0.15 / gift_card 0.08.
  Independent of basket value.
- **refund_method (`returns`).** original_payment 0.70 / store_credit 0.22 / exchange 0.08.
  Independent of `reason` and `restocked`.

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
- **`restocked` is keyed only to `reason`.** Restock likelihood is a per-reason probability
  (mind-change/fit ~0.9, defective/damaged ~0.05) with no mediating item condition — a clean,
  causally-sensible step by reason. Adding a `returns.item_condition` covariate is tracked as
  field-enrichment in `TODO.md`, not a realism bug.
- **Return propensity and reason depend only on category** — not on price, customer segment,
  channel, quantity, or season. A real store would couple returns to fit/size data and customer
  history; here category is the sole covariate (the planted signal).
- **`segment` and `channel` carry no signal** — they're drawn independently of order value,
  return behavior, and each other; they exist for slicing practice, not a planted
  segment/channel scenario (natural future additions).
- **The added descriptive fields carry no signal either** —
  `customers.acquisition_channel` / `customers.marketing_opt_in`, `orders.payment_method`,
  and `returns.refund_method` are all drawn independently of value and return behaviour
  (slicing practice, not planted signals). `products.brand` is uniform *within* category, so
  it inherits the category gradient rather than adding one, and `products.weight_kg` is a
  category-keyed covariate not yet wired into shipping cost or damage-in-transit returns.

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

-- Q4 seasonality: Nov+Dec carry ~0.31 of a year's orders (a flat calendar gives ~0.167)
select sum(case when extract(month from order_date) in (11, 12) then 1 else 0 end)::float
       / count(*) as q4_share
from orders;

-- product names are mostly distinct (~0.95; guards against the adjective+noun lattice)
select count(distinct product_name)::float / count(*) as distinct_name_ratio from products;
```
