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

### 1. `products.cost` → gross margin ✅ flat column shipped 2026-07-11
- [x] Unit cost (`Float64`, `round(unit_price × (1 − margin), 2)` with a **flat**
      category-independent margin (Normal(0.45, 0.05) clamped [0.05, 0.90]), so
      `0 < cost < unit_price` always). Child stream `margin`; existing columns byte-identical.
      See `products.py` + realism-log.
- **Unlocks:** the central retail metric — gross margin per line, per order, per category;
  margin-adjusted basket value.
- **Class:** **scenario-bearing** — the flat column is shipped (realism). Candidate signal:
  margin differs sharply by category (electronics thin, apparel fat) — the inverse of the
  return-rate gradient, so high-return categories may also be high-margin. **Deferred**: the
  per-category gradient stays for `/scenario:draft-or-propose`, not planted here.

### 2. `orders.discount_amount` / `promo_code` ✅ flat columns shipped 2026-07-11
- [x] An order-level discount (`Float64`, 0 for ≈0.85 of orders, else a **fixed** dollar tier
      from {5,10,15,20,25}) and a nullable `promo_code` (`Utf8`, uniform over a 5-code catalog).
      Fixed, not merchandise-proportional — the header can't see basket lines without a
      build-order cycle. `discount_amount > 0` iff `promo_code` not null. Child streams
      `promo` / `discount`; existing columns byte-identical. See `orders.py` + realism-log.
- **Unlocks:** promotion analysis — discount depth, promo penetration, net vs. gross basket.
- **Class:** **scenario-bearing** — flat columns shipped (realism). Candidate signal: discounted
  orders return *more* (deal-seekers) or bigger baskets — **deferred** to
  `/scenario:draft-or-propose`, kept independent of returns/basket here.

### 3. `orders.shipping_fee` + `tax_amount` ✅ shipped 2026-07-11 as the `order_charges` table
- [x] Shipping fee (`Float64`, keyed to basket value — free over a threshold) and tax
      (derived from merchandise × a rate). **Shipped as a new order-grain `order_charges` table**,
      not columns on `orders`: `orders` builds *before* `order_items`, so the header can't see its
      own basket merchandise without a build-order cycle. `order_charges` (one row per order, built
      after the fan-out) carries `merchandise` = `round(Σ line_total, 2)`, `shipping_fee` (free
      ≥\$50 else tiered \$4.99/\$7.99), and `tax_amount` = `round(0.0725 × merchandise, 2)`. Pure
      function of `orders` + `order_items` — **no draws**, so every existing table is byte-identical.
      See `order_charges.py` + realism-log.
- **Unlocks:** true order total (merchandise + shipping + tax − discount), free-shipping-threshold
  behaviour, checkout economics.
- **Class:** realism enrichment — composes with the derived basket value the collection already
  teaches (the "excludes tax/shipping" simplification is reconciled: true total is now a derived
  identity over `order_charges`, `merchandise` stays the base for the right-skew scenario).

### 4. `returns.item_condition` → reverse logistics ✅ shipped 2026-07-02
- [x] Condition on arrival (`Utf8`: resellable / opened / damaged), keyed to `reason`
      (defective/damaged rarely resellable), and `restocked` now keys off it. See
      `returns.py` (`_CONDITION_MIX` / `_RESTOCK_BY_CONDITION`) + realism-log.
- **Unlocked:** reverse-logistics recovery rate (overall ≈ resellable 0.51 / damaged 0.27 /
  opened 0.22); ties `restocked` to a cause via `reason → item_condition → restocked`.
- **Class:** realism enrichment — resolved the standing "restocked keyed only to reason" note.

### 5. `order_items.discount_pct` ✅ shipped 2026-07-11
- [x] Per-line promotional discount (`Float64`, 0 for ≈0.82 of lines, else a tier from
      {0.10..0.40}). `line_total` kept **gross**; net line value is the derived identity
      `line_total × (1 − discount_pct)`, not stored — so a gross-vs-net line comparison is
      possible without mutating the pinned `line_total` identity. Child stream `discount_pct`;
      existing columns byte-identical. See `order_items.py` + realism-log.
- **Unlocks:** line-level markdown analysis; interacts with item 1's margin.
- **Class:** realism enrichment — flat markdown, carries no signal.

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

- [x] **Revise `realism-guidance.md`.** _Done 2026-07-11._ The rubric + invariant tests are
      reconciled with every landed column/table: `0 < cost < unit_price`, `discount_amount > 0`
      iff `promo_code`, `discount_pct ∈ [0, 0.6]`, `item_condition`↔`restocked`, and the
      `order_charges` invariants (one-per-order, `merchandise = round(Σ line_total, 2)`,
      `shipping_fee = 0` at/above the \$50 free threshold, the tax identity, non-negativity) plus
      the derived-true-total edge case. Each column/table landed with its own reconcile + pinned
      test (see `realism-log.md`), so no separate `/data-collection:review-edit-regen-for-realism`
      sweep was needed.
