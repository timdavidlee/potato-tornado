# Retail — dated working checklist (2026-07-11 12:28)

- **Scope:** the `retail` collection only.
- **Source of truth:** [`collections/retail/TODO.md`](../../src/potato_tornado/collections/retail/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/retail/realism-log.md). Workflow lives in
  [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** all high-leverage items shipped. Quick wins + `returns.item_condition` earlier;
  `discount_pct` and the flat `cost` / `promo` columns landed 2026-07-11; `shipping_fee` +
  `tax_amount` shipped 2026-07-11 as the new order-grain `order_charges` table (the structurally
  clean fix for the build-order dependency). Realism-guidance revised.

## Checklist

**High-leverage columns →** [`TODO.md` § High-leverage additions](../../src/potato_tornado/collections/retail/TODO.md#high-leverage-additions)

- [x] `products.cost` *(2026-07-11 — flat; margin-by-category signal deferred)*
- [x] `orders.discount_amount` + `orders.promo_code` *(2026-07-11 — flat)*
- [x] `orders.shipping_fee` + `orders.tax_amount` *(2026-07-11 — shipped as the `order_charges` order-grain totals table, not columns on `orders`)*
- [x] `order_items.discount_pct` *(2026-07-11)*

**When the list is done →** [`TODO.md` § When the list is done](../../src/potato_tornado/collections/retail/TODO.md#when-the-list-is-done)

- [x] Revise `realism-guidance.md` for `shipping_fee`/`tax_amount` *(2026-07-11 — done alongside the table)*
