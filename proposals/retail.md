# retail — collection proposal

- **Domain:** an online store where customers place orders, each order is a basket
  of one or more line items, and a fraction of those items come back as returns.
- **Teaching value:** the first collection with a genuine **one-to-many basket
  fan-out** — an `orders` header with a variable number of `order_items` children —
  so students learn header/line aggregation (basket value = Σ line totals, item
  counts, join-and-group-by) rather than the 1:1 parent→child chains the existing
  four use. It also carries a **category-dependent return funnel**: return
  propensity and reason mix differ sharply by product category, a covariate signal
  distinct from clinic's lead-time gradient or hotel's channel mix.

## Tables

Build order (a DAG): `customers`, `products` → `orders` → `order_items` →
`returns`.

- `customers` — the buyer dim. Columns: `customer_id: Utf8` (`CUS-000001`),
  `full_name: Utf8` + `email: Utf8` (from `ctx.entities.people`),
  `city: Utf8` (from `ctx.entities.cities`), `signup_date: Date` (spread across the
  window), `segment: Utf8` (`new`/`returning`/`vip`, weighted). `depends_on=()`.

- `products` — the catalog dim. Columns: `product_id: Utf8` (`SKU-00001`),
  `product_name: Utf8`, `category: Utf8` (from `constants.CATEGORIES`),
  `unit_price: Float64` (right-skew). `depends_on=()`.

- `orders` — the basket header, one row per order. Columns: `order_id: Utf8`
  (`ORD-0000001`), `customer_id: Utf8 → customers.customer_id`,
  `order_date: Date` (spread across the window),
  `channel: Utf8` (`web`/`mobile`/`marketplace`, weighted),
  `status: Utf8` (`delivered`/`shipped`/`cancelled`),
  `item_count: Int64` (the basket's realized line count).
  `depends_on=("customers",)`.

- `order_items` — the **fan-out**: `item_count` lines per order. Columns:
  `order_item_id: Utf8` (`OIT-00000001`),
  `order_id: Utf8 → orders.order_id`,
  `product_id: Utf8 → products.product_id`,
  `quantity: Int64`, `unit_price: Float64` (snapshot of the product price),
  `line_total: Float64` (`= round(quantity × unit_price, 2)`).
  `depends_on=("orders", "products")`.

- `returns` — the subset of line items sent back. Columns: `return_id: Utf8`
  (`RET-0000001`), `order_item_id: Utf8 → order_items.order_item_id` (at most one
  return per line), `order_id: Utf8 → orders.order_id`,
  `return_date: Date` (≥ the order date), `reason: Utf8` (from
  `constants.RETURN_REASONS`), `refund_amount: Float64` (≤ the line total),
  `restocked: Boolean`. `depends_on=("order_items", "orders")`.

**Basket value is a derived aggregate**, not a stored header column: an order's
total is `sum(order_items.line_total)` for that `order_id`. Keeping it out of
`orders` is deliberate — computing it is the join-and-group-by teaching point — and
it sidesteps a redundant column that would have to be kept in lockstep with the
fan-out. The header's `item_count` is planted to equal the realized number of
`order_items` rows (an invariant a reviewer can check).

## Constants

`constants.py` candidates (each used by two or more tables):

- `CATEGORIES` — `(category_name, price_median, base_return_rate)` rows; read by
  `products` (price + category) and by `returns` (the per-category return
  propensity and reason mix).
- `RETURN_REASONS` — the reason ladder
  (`changed_mind`/`too_small`/`defective`/`not_as_described`/`damaged_in_transit`),
  shared by `returns` and referenced by the realism/scenario docs.

Single-table literals (channel list, segment weights) stay inline in their module.

## Distributions & target magnitudes

All numbers are **targets to plant**, to be firmed up after the first generation.

- **Row counts (`scale=1.0`):** `customers` = `ctx.n(3000)`,
  `products` = `ctx.n(500)`, `orders` = `ctx.n(12000)`,
  `order_items` ≈ 2.3 × orders (variable), `returns` ≈ 10% of `order_items`.
- **unit_price:** `ctx.dist.lognormal(median≈22, sigma≈0.7)`, clamped `[1, 500]` —
  most items cheap, a long premium tail. `category` shifts the median.
- **item_count per order:** `1 + Poisson(λ≈1.5)` → mostly 1–3 items, tail to ~8,
  mean ≈ 2.3.
- **quantity per line:** 1 (0.80) / 2 (0.15) / 3+ (0.05).
- **order_date:** `ctx.dist.dates_between(start_date, end_date)` — uniform across
  the full ~3-year window.
- **channel mix:** web 0.50 / mobile 0.40 / marketplace 0.10.
- **order status:** delivered 0.90 / shipped 0.05 / cancelled 0.05.
- **return rate (category-driven):** apparel ≈ 22%, electronics ≈ 10%, home ≈ 6%,
  consumables ≈ 2% → overall ≈ 10%.
- **return reason mix:** apparel skews `changed_mind` + `too_small`; electronics
  skews `defective` + `not_as_described`; `damaged_in_transit` is small and roughly
  flat across categories.
- **refund_amount:** full line refund 0.90; else a partial refund (restocking fee)
  0.6–0.9 × `line_total`. `return_date` = order date + 5–30 day delay, within window.

## Candidate scenarios

- **Return rate varies sharply by product category.** Signal: apparel is returned
  many times more often than consumables. Tables: `returns.order_item_id`,
  `order_items.product_id`, `products.category`. Target: apparel ≈ 22% vs
  consumables ≈ 2% (~10×), overall ≈ 10%. How to find it: join
  `returns → order_items → products`, `group by category`,
  `avg(returned::int)` over all `order_items` — rate climbs by category.

- **Order value is right-skewed and basket-size driven.** Signal: most baskets are
  small; a heavy tail comes from multi-item and high-price orders. Tables:
  `order_items.line_total` aggregated to `order_id`. Target: median basket ≈ \$35,
  p95 ≈ \$180. How to find it: `select order_id, sum(line_total) v from order_items
  group by order_id;` then `quantile(v, 0.5)`, `quantile(v, 0.95)`.

- **Return reasons differ by category** (`changed_mind`/`too_small` dominate
  apparel). Signal: the reason mix is category-specific, not uniform. Tables:
  `returns.reason`, `order_items.product_id`, `products.category`. Target: in
  apparel, `changed_mind` + `too_small` ≈ 60% of returns; `defective` leads only in
  electronics. How to find it: join to category, `group by category, reason`,
  compare shares.

## Realism guidance (seed)

**Invariants — must always hold:**
- Referential integrity: `orders.customer_id ∈ customers`;
  `order_items.order_id ∈ orders` and `order_items.product_id ∈ products`;
  `returns.order_item_id ∈ order_items` (each line returned at most once) and
  `returns.order_id ∈ orders`.
- Fan-out consistency: `orders.item_count` equals the number of `order_items` rows
  for that order.
- Arithmetic identities: `line_total = round(quantity × unit_price, 2)`;
  `refund_amount ≤ line_total`.
- Temporal ordering: `return_date ≥ order_date`; both within the window;
  `order_date ≥ customers.signup_date` for that customer.
- Non-negativity / bounds: `quantity ≥ 1`, `unit_price > 0`, `refund_amount > 0`.

**Deliberate simplifications — intended, do not "fix":**
- No price history: a line's `unit_price` is the current product price — no
  promotions, discounts, or per-order pricing.
- One return per line item, whole-line only — no partial-quantity returns.
- Order value excludes taxes and shipping; there is no shipping/fees table.
- No inventory or stock constraints; any product can appear on any order.

## Building it

Follows the "Adding a collection" checklist in
[collections/CLAUDE.md](../src/potato_tornado/collections/CLAUDE.md): package
`collections/retail/` with `__init__.py`, `constants.py`, `tables/`
(`customers`, `products`, `orders`, `order_items`, `returns`), `scenarios/`,
`realism-guidance.md`; `register("retail", build)`; add
`"potato_tornado.collections.retail"` to `_BUILTIN_MODULES`; README row; tests
mirrored under `tests/collections/retail/`.

**Core APIs it leans on (all exist today):** `ctx.entities.people` (customers),
`ctx.entities.cities`, `ctx.dist.lognormal` / `choice` / `integers` / `poisson` /
`dates_between`, `ctx.n(base)`, `ctx.table(...)`.

**New helpers needed — none.** The variable-length `order_items` fan-out follows
the list-extend loop idiom
([`labor/tables/assignments.py`](../src/potato_tornado/collections/labor/tables/assignments.py)).
The category-driven return propensity is a **per-row** probability, and
`ctx.dist.bernoulli(n, p)` only takes a scalar `p` — as `labor` already does, drop
to `ctx.rng.numpy` and compare a per-row probability array
(`ctx.rng.numpy.random(n) < p_array`) rather than adding a vectorized-`p` helper.
