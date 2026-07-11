# Retail high-leverage economics columns — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `retail` collection only.
- **Source:** [`collections/retail/TODO.md`](../../src/potato_tornado/collections/retail/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/retail/realism-log.md)).
- **Status:** all **6 quick wins** shipped and high-leverage item 4 (`returns.item_condition`)
  shipped; the first too-synthetic sweep is done, so realism is **Converged** (all 5 open realism
  items resolved). Open: the **4 remaining high-leverage economics columns** below.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism retail`
  (build flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset signal*
  goes through `/scenario:draft-or-propose retail` then `/scenario:review-and-edit-regenerate`.
  Don't plant the signal during the realism pass.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` / `ctx.entities`
on a **name-keyed child stream** without reordering existing draws; reconcile the matching line in
`realism-guidance.md`; add/extend an invariant test in
`tests/collections/retail/test_retail.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## High-leverage columns

- [ ] **`products.cost`** (`Float64`) → gross margin
  - File: `tables/products.py`. Draw: `unit_price × (1 − margin)` with a per-category margin band,
    so `cost < price` always; own child stream.
  - Unlocks: the central retail metric — gross margin per line / order / category; margin-adjusted
    basket value.
  - Class: **scenario-bearing** → *margin differs sharply by category (electronics thin, apparel
    fat)* — the inverse of the return-rate gradient, so high-return categories may also be
    high-margin.

- [ ] **`orders.discount_amount`** (`Float64`, 0 for most) + nullable **`orders.promo_code`** (`Utf8`)
  - File: `tables/orders.py`. Draw: an order-level discount as a share of merchandise for the
    discounted minority; own child stream.
  - Unlocks: promotion analysis — discount depth, promo penetration, net vs. gross basket.
  - Class: **scenario-bearing** → *discounted orders return more (deal-seekers) or carry bigger
    baskets* — a promo-quality subset signal.

- [ ] **`orders.shipping_fee`** (`Float64`) + **`orders.tax_amount`** (`Float64`)
  - File: `tables/orders.py`. Draw: shipping fee keyed to basket value (free over a threshold);
    tax derived from merchandise × a rate; own child stream.
  - Unlocks: true order total (merchandise + shipping + tax), free-shipping-threshold behaviour,
    checkout economics.
  - Class: **realism** — composes with the derived basket value (documented today as *excluding*
    tax/shipping; reconcile that simplification in the same change).

- [ ] **`order_items.discount_pct`** (`Float64`, mostly 0)
  - File: `tables/order_items.py`. Draw: per-line promotional discount so `line_total` reflects the
    net price; own child stream.
  - Unlocks: line-level markdown analysis; interacts with `products.cost` margin.
  - Class: **realism** — note: changes the `line_total` identity; reconcile in
    `realism-guidance.md` if net-of-discount.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** Reconcile the rubric and invariant tests with the new
  columns (e.g. `cost < unit_price`, `shipping_fee = 0` above the free threshold,
  `line_total` net-of-`discount_pct`).

_Out of scope: a per-order `shipments` / fulfillment table is a new entity → `/data-collection:propose`
(and `logistics` already models parcel delivery)._

---

## Suggested order

1. **`products.cost`** — the central margin lever; build flat, then route the margin-by-category
   surprise to `/scenario:draft-or-propose retail`.
2. **`orders.shipping_fee` + `tax_amount`** — realism; completes the true order total and settles
   the basket-value-excludes-tax/shipping simplification.
3. **`orders.discount_amount` / `promo_code`** then **`order_items.discount_pct`** — the promo pair;
   land the line-level markdown alongside the order-level discount so the `line_total` identity is
   reconciled once.
