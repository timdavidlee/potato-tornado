# retail — field-enrichment TODO

Candidate columns to add to the existing `retail` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

Context: an online store with a header/line basket fan-out — `customers` place `orders` of
`order_items`, a category-dependent share come back as `returns`. Basket value is a derived
`sum(line_total)`. The current schema has **no product cost (so no margin), no order-level
economics (discounts, shipping, tax), no acquisition/marketing dimension, and no returns
disposition** — so profitability, promo lift, and reverse-logistics can't be measured. The
additions below close those gaps.

## Quick wins (realism enrichment)

_All six shipped (see `realism-log.md`, 2026-07-02). Brand/weight live inline in
`products.py` (single-table literals) rather than `constants.py`, and all new draws use
name-keyed child streams so existing columns/tests are byte-identical._

- [x] **`products.brand`** (`Utf8`) — uniform over a per-category house catalog (`_BRANDS` in
      `products.py`). Unlocks: brand-level sales / return slicing.
- [x] **`products.weight_kg`** (`Float64`) — per-category lognormal, clamped [0.05, 30]. Unlocks:
      shipping-cost modelling; a covariate for `damaged_in_transit` returns (not yet wired).
- [x] **`orders.payment_method`** (`Utf8`) — {card, paypal, gift_card, bnpl} weighted. Unlocks:
      tender mix; a BNPL-vs-card cut.
- [x] **`customers.acquisition_channel`** (`Utf8`) — {organic, paid_search, social, referral,
      email} weighted. Unlocks: acquisition-source analysis alongside `segment`.
- [x] **`customers.marketing_opt_in`** (`Boolean`) — Bernoulli(0.60). Unlocks:
      addressable-audience sizing.
- [x] **`returns.refund_method`** (`Utf8`) — {original_payment, store_credit, exchange}.
      Unlocks: refund-disposition mix; composes with `refund_amount`.

## High-leverage additions

### 1. `products.cost` → gross margin
- [ ] Unit cost (`Float64`, `unit_price × (1 − margin)` with a per-category margin band, so
      cost < price always).
- **Unlocks:** the central retail metric — gross margin per line, per order, per category;
  margin-adjusted basket value.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: margin
  differs sharply by category (electronics thin, apparel fat) — the inverse of the return-rate
  gradient, so high-return categories may also be high-margin. Name it; don't plant it here.

### 2. `orders.discount_amount` / `promo_code`
- [ ] An order-level discount (`Float64`, 0 for most orders, else a share of merchandise) and a
      nullable `promo_code` (`Utf8`).
- **Unlocks:** promotion analysis — discount depth, promo penetration, net vs. gross basket.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: discounted
  orders return *more* (deal-seekers) or bigger baskets — a promo-quality subset signal.

### 3. `orders.shipping_fee` + `tax_amount`
- [ ] Shipping fee (`Float64`, keyed to basket value — free over a threshold) and tax
      (derived from merchandise × a rate).
- **Unlocks:** true order total (merchandise + shipping + tax), free-shipping-threshold
  behaviour, checkout economics.
- **Class:** realism enrichment — composes with the derived basket value the collection already
  teaches (documented today as *excluding* tax/shipping; reconcile that simplification).

### 4. `returns.item_condition` → reverse logistics
- [ ] Condition on arrival (`Utf8`: resellable / damaged / opened), correlated with `reason`
      (defective/damaged rarely resellable — this is what `restocked` should key off).
- **Unlocks:** reverse-logistics recovery rate; ties the existing `restocked` flag to a cause.
- **Class:** realism enrichment — directly addresses the standing realism note that
  `restocked` is keyed only to `reason`.

### 5. `order_items.discount_pct`
- [ ] Per-line promotional discount (`Float64`, mostly 0), so `line_total` reflects the net
      price and a gross-vs-net line comparison is possible.
- **Unlocks:** line-level markdown analysis; interacts with item 1's margin.
- **Class:** realism enrichment (note: changes the `line_total` identity — reconcile in
  `realism-guidance.md` if net-of-discount).

## Out of scope (new table, not a field)

- **A per-order `shipments` / fulfillment table** (carrier, tracking, delivery date) is a new
  entity, not a column on `orders` — route to `/data-collection:propose` (and note the
  `logistics` collection already models parcel delivery).

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items. **First dedicated realism sweep done 2026-07-02** (see `realism-log.md`) —
all five items resolved (two fixed, three judged deliberate).

- [x] **Returns depend on category and nothing else.** _Judged deliberate_ — confirmed flat by
      segment (0.11–0.12), channel, and within-category price (apparel hi/lo 0.224 vs 0.236).
      This is the collection's planted signal (category is the sole covariate); coupling returns
      to price/segment would be a **scenario**, not a realism fix. Documented under
      "Deliberate simplifications".
- [x] **Product-name lattice.** _Fixed_ — added a per-category qualifier word and widened
      adjectives to 12 (`adjective × qualifier × noun`, ~432 combos/category); distinct names
      rose from 173 → 433 of 500 (≤3 dupes). See `products.py` + realism-log.
- [x] **No calendar seasonality.** _Fixed_ — `order_date` now sampled with a repeating Q4 peak
      (Nov ×1.4 / Dec ×1.55, Feb trough ×0.80); Nov+Dec ≈ 0.31 of a year's orders and the peak
      recurs each year. See `orders.py` (`_MONTH_SEASONALITY`) + realism-log.
- [x] **`unit_price` per category is a single lognormal median.** _Verified fine_ — 482/500
      distinct prices, continuous cents (no round-number clustering), only 1 SKU at the \$500
      clamp, believable premium tail. No change needed.
- [x] **`restocked` is keyed only to reason.** _Judged deliberate_ — the per-reason step
      (mind-change/fit ~0.9, defective/damaged ~0.05) is causally sensible. The natural
      enhancement is the `returns.item_condition` field (high-leverage item 4 above), tracked as
      field-enrichment, not a realism bug.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
      rubric and invariant tests with the new columns (new dimensions to slice by, new
      invariants — e.g. `cost < unit_price`, `shipping_fee = 0` above the free threshold,
      `item_condition` correlated with `restocked`). Run
      `/data-collection:review-edit-regen-for-realism` for this collection.
