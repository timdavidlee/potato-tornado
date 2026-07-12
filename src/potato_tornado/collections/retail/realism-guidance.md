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
  `returns.order_item_id ∈ order_items` and `returns.order_id ∈ orders`;
  `order_charges.order_id ∈ orders`.
- **Order-charges grain.** Exactly one `order_charges` row per order (`order_id` unique and
  covers every order). `merchandise = round(Σ order_items.line_total, 2)` for that order — it
  must reconcile to the fan-out. `shipping_fee` follows the threshold rule (0 when
  `merchandise ≥ 50`, else 4.99 when `merchandise ≥ 25`, else 7.99);
  `tax_amount = round(0.0725 × merchandise, 2)`. All three are ≥ 0.
- **One return per line, at most.** `order_item_id` is unique in `returns` (a line is returned
  zero or one times, never split).
- **Inspection notes render the structured disposition.** Every `returns.inspection_note` is a
  free-text warehouse note that renders *that return's* `item_condition` and `restocked` (never
  a re-sampled second draw): parsing the note's arrival-condition phrase recovers
  `item_condition` and its disposition phrase recovers `restocked`, exactly, for every row. The
  note never names the product category, so recovery-by-category is only recoverable via the
  `order_items → products` join. See `scenarios/recovery-rate-hides-in-inspection-notes.md`.
- **Fan-out consistency.** `orders.item_count` equals the number of `order_items` rows for that
  order (`sum(item_count) == order_items.height`).
- **Arithmetic identities.** `line_total = round(quantity × unit_price, 2)` — kept **gross**
  (pre-discount); `refund_amount ≤ line_total`. The net line value is the *derived* identity
  `line_total × (1 − discount_pct)`, not a stored column.
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
  `returns.item_condition ∈ {resellable, opened, damaged}`;
  `products.brand ∈` the row category's brand catalog.
- **Non-negativity / bounds (added fields).** `products.weight_kg ∈ [0.05, 30]`;
  `0 < products.cost < products.unit_price` (every SKU has a real positive gross margin).

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `customers` = 3000, `products` = 500, `orders` = 12000,
  `order_items` ≈ 2.5 × orders (≈ 30k, variable), `returns` ≈ 12% of `order_items` (≈ 3.5k),
  `order_charges` = 12000 (one per order).
- **unit_price.** Lognormal (σ ≈ 0.7) with a per-category median (apparel \$22 / electronics
  \$55 / home \$26 / consumables \$8), clamped to [\$1, \$500]. Overall median ≈ **\$23**, a
  long premium tail. Cents are continuous (not charm-priced) and prices don't cluster on
  round numbers; ~0.96 of SKUs carry a distinct price (no lattice).
- **cost (`products`).** `round(unit_price × (1 − margin), 2)` where `margin` is drawn from a
  **per-category mean** (apparel ≈ 0.58 / home ≈ 0.45 / consumables ≈ 0.42 / electronics ≈
  0.28) with a small within-category Normal sd ≈ 0.05, clamped to [0.05, 0.90] — so
  `0 < cost < unit_price` always and gross margin runs **against** the return-rate gradient
  (apparel is both highest-return and fattest-margin; electronics thinnest). Overall gross
  margin averages ≈ **0.46**. A ~30-point apparel→electronics spread. See
  `scenarios/margin-differs-by-category.md`.
- **product_name.** `adjective × per-category qualifier × noun` (12 × 6 × 6 ≈ 432 combos per
  category), so duplicate names are rare — ≈ **0.95** of the 500 SKUs carry a distinct name. A
  synthetic label for joins, not a real SKU master.
- **Category mix.** apparel 0.34 / home 0.26 / consumables 0.22 / electronics 0.18.
- **item_count per order.** `1 + Poisson(1.5)` → mostly 1–3 items, tail to ~8, mean ≈ **2.5**.
- **quantity per line.** 1 (0.80) / 2 (0.15) / 3 (0.05).
- **discount_pct per line (`order_items`).** 0 for ≈ **0.82** of lines (sold at sticker); the
  remaining ≈ 0.18 carry a markdown drawn uniformly from the tier ladder {0.10, 0.15, 0.20,
  0.25, 0.30, 0.40}. `line_total` stays gross; net line value is the derived
  `line_total × (1 − discount_pct)`. Carries no signal — drawn independently of product,
  basket, and return behaviour.
- **Basket value.** `sum(line_total)` per order is right-skewed: median ≈ **\$80**, p95 ≈
  **\$290**, mean ≈ \$107. Materialized order-grain as `order_charges.merchandise` (round of the
  sum, exact to the cent), but still not on the `orders` header. See
  `scenarios/order-value-right-skew.md`.
- **shipping_fee / tax_amount (`order_charges`).** `shipping_fee` is free (0) once
  `merchandise ≥ \$50` — ≈ **0.70** of orders — else a two-step tier (\$4.99 when
  `merchandise ≥ \$25`, \$7.99 below that), so the fee avoids a single-value lattice.
  `tax_amount` is a flat **7.25%** of `merchandise` (`round(0.0725 × merchandise, 2)`). Both are
  a pure-deterministic function of the fan-out — no independent draws.
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
  total.
- **item_condition (`returns`).** Arrival condition keyed to `reason`: mind-change/fit returns
  arrive mostly `resellable` (~0.75), defect/damage returns mostly `damaged` (~0.80–0.87),
  `not_as_described` mixed. Overall ≈ resellable 0.51 / damaged 0.27 / opened 0.22.
- **restocked.** Keyed to `item_condition` (which is reason-driven), not `reason` directly:
  resellable ~0.97 / opened ~0.50 / damaged ~0.04. The mediated restock-by-reason gradient is
  fit/mind-change ~0.85, `not_as_described` ~0.63, defective/damaged ~0.08–0.15. Resale-recovery
  rolled up **by category** runs *against* the return-rate gradient — apparel ≈ 0.68 (highest
  return AND highest recovery) / consumables ≈ 0.52 / home ≈ 0.47 / electronics ≈ 0.45 (overall
  ≈ 0.62). See `scenarios/recovery-rate-hides-in-inspection-notes.md`.
- **inspection_note (`returns`).** Free-text warehouse note, one per return, over 3 template
  layouts × 3 phrasings per condition/disposition (name-keyed off `ctx.rng`). Pure rendering of
  `item_condition` + `restocked` — carries no independent draw and no signal of its own beyond
  the two columns it renders.
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
- **promo_code / discount_amount (`orders`).** ≈ **0.15** of orders carry a `promo_code`
  (nullable `Utf8`, uniform over a 5-code catalog: `WELCOME10` / `SAVE15` / `SPRING20` /
  `FREESHIP` / `LOYALTY25`); those orders get a `discount_amount` drawn as a **fixed** dollar
  tier from {\$5, \$10, \$15, \$20, \$25} (uniform, independent of the code). Non-promo orders
  have a null code and `discount_amount = 0`, so `discount_amount > 0` iff `promo_code` is not
  null. The discount is a fixed amount, **not** a share of merchandise (the header can't see
  basket lines without a build-order cycle), and carries no signal — independent of returns and
  basket size. The discounted-orders-return-more subset signal is a **deferred scenario**.
- **refund_method (`returns`).** original_payment 0.70 / store_credit 0.22 / exchange 0.08.
  Independent of `reason` and `restocked`.

## Deliberate simplifications (intended — do not "fix")

- **No stored basket total on the header.** `orders` still has no `order_total`; the basket's
  merchandise subtotal is deliberately a `sum(order_items.line_total)` aggregate (the
  join-and-group-by teaching point). It *is* now materialized order-grain as
  `order_charges.merchandise` — but on a separate post-fan-out table, not the `orders` header, and
  it must reconcile to the fan-out (`merchandise = round(Σ line_total, 2)`), so nothing can drift.
  `item_count` *is* stored on the header and pinned to the realized line count.
- **No price history.** A line's `unit_price` is a snapshot of the current product price — the
  same product on two orders shows the same sticker price (no per-order/per-customer pricing).
  A per-line `discount_pct` records a flat markdown on top, but it carries no signal and
  `unit_price` itself never varies.
- **One return per line, whole-line only** — no partial-quantity returns (you can't return 1
  of a quantity-3 line) and no re-returns.
- **Order total is a derived identity (not stored).** `order_charges` carries the
  `merchandise` subtotal, `shipping_fee`, and `tax_amount`, but not an `order_total`: the true
  total is the *derived* identity `merchandise + shipping_fee + tax_amount −
  orders.discount_amount` (kept unstored, like every other total here). `merchandise` alone
  stays the base for the order-value-right-skew scenario. **Edge case (do not clamp):** because
  `discount_amount` is a *fixed* dollar tier drawn independently of basket size (see the
  promo note above), the derived true total can go slightly **negative** for a few tiny,
  high-discount baskets (≈ **0.5%** of orders) — a known artifact inherited from the fixed
  discount, left as-is rather than clamped.
- **No inventory or stock model.** Any product can appear on any order in any quantity; there
  are no stockouts, and `restocked` doesn't feed back into available inventory.
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
  `order_items.discount_pct` is a flat markdown drawn independently of product / basket /
  return behaviour (the discounted-orders-return-more subset signal is a deferred scenario).

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

-- gross margin by category runs against the return gradient: apparel ~0.58 (fattest AND
-- highest-return) → electronics ~0.28 (thinnest); home ~0.44 / consumables ~0.42 in between
select category, avg((unit_price - cost) / unit_price) as gross_margin
from products group by category order by gross_margin desc;

-- Q4 seasonality: Nov+Dec carry ~0.31 of a year's orders (a flat calendar gives ~0.167)
select sum(case when extract(month from order_date) in (11, 12) then 1 else 0 end)::float
       / count(*) as q4_share
from orders;

-- product names are mostly distinct (~0.95; guards against the adjective+noun lattice)
select count(distinct product_name)::float / count(*) as distinct_name_ratio from products;

-- restock keys off arrival condition (~0.97 resellable / ~0.50 opened / ~0.04 damaged)
select item_condition, avg(restocked::int) as restock_rate
from returns group by item_condition order by restock_rate;

-- order_charges reconcile to the fan-out + shipping/tax identities (expect 0 each)
select count(*) filter (where oc.merchandise <> agg.m)                       as bad_merch,
       count(*) filter (where oc.merchandise >= 50 and oc.shipping_fee > 0)  as bad_free_ship,
       count(*) filter (where round(0.0725 * oc.merchandise, 2) <> oc.tax_amount) as bad_tax
from order_charges oc
join (select order_id, round(sum(line_total), 2) as m from order_items group by order_id) agg
  using (order_id);

-- free-shipping penetration: ~0.70 of orders ship free (merchandise >= $50)
select avg((shipping_fee = 0)::int) as free_ship_share from order_charges;
```
