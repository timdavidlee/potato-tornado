# Realism log — retail

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — the first dedicated too-synthetic sweep has run (2026-07-02): the two
real artifacts (product-name lattice, no calendar seasonality) are fixed, and the remaining
open items are confirmed deliberate simplifications (category-only returns, reason-only
restock) documented in `realism-guidance.md`. (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Initial build + basket-value price re-tune.** Pinned the invariants
  (header/line fan-out consistency `item_count == #order_items`, `line_total` identity,
  `refund ≤ line_total`, `order_date ≥ signup`, `return_date ≥ order_date`). Lowered the
  per-category price medians so `unit_price` median ≈ \$22 and basket value median ≈ \$80 (the
  proposal's \$35 basket was inconsistent with a \$22 item median × ~2.5 items). Verified the
  category return-rate gradient (2% → 22%) and category-specific reason mixes. (`13793d9`)
- **2026-07-02 — First too-synthetic sweep.** Ran the 2b synthetic-artifact sweep over all
  five open realism items. **Fixed two:** (1) *product-name lattice* — names were
  `adjective × noun` (8 × 6 = 48 combos/category), giving only **173 distinct names / 500 SKUs**
  (up to 9 dupes); added a per-category qualifier word and widened adjectives to 12
  (`adj × qual × noun`, ~432 combos), lifting distinctness to **433 / 500** (≤3 dupes). (2) *no
  calendar seasonality* — `order_date` was uniform in `[base, end)`, which (via accumulating
  signups) produced a ~6x monotonic ramp and **no within-year cycle**; replaced with
  inverse-CDF sampling over per-day month-seasonality weights (Q4 peak Nov ×1.4 / Dec ×1.55,
  Feb trough ×0.80), so Nov+Dec now hold ≈ **0.31** of a year's orders and the peak repeats
  each year (invariants unchanged: `order_date ∈ [signup, end)`). **Judged three deliberate
  (documented, not bugs):** category-only return propensity (flat by segment/channel/price —
  the planted signal; coupling would be scenario work), reason-only `restocked` (a
  causally-sensible step; `item_condition` mediation is field-enrichment), and `unit_price`
  (482/500 distinct, no round-number lattice, believable tail — verified fine). Reconciled
  `realism-guidance.md` (new order_date + product_name distributions, restock simplification,
  two review queries) and pinned tests (`order_date` window bound, name distinctness, Q4 share).

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a `products.cost`
  margin signal) to [`TODO.md`](TODO.md). No columns implemented yet — the backlog is the open
  work.
- **2026-07-02 — Quick-wins shipped (6 columns).** Implemented all six quick-win fields:
  `products.brand` (uniform over a per-category `_BRANDS` catalog) + `products.weight_kg`
  (per-category lognormal, clamped [0.05, 30]); `orders.payment_method`
  (card 0.55 / paypal 0.22 / bnpl 0.15 / gift_card 0.08); `customers.acquisition_channel`
  (organic 0.30 / paid_search 0.25 / social 0.20 / email 0.13 / referral 0.12) +
  `customers.marketing_opt_in` (Bernoulli 0.60); `returns.refund_method`
  (original_payment 0.70 / store_credit 0.22 / exchange 0.08). All drawn from name-keyed
  child streams (`brand`, `weight`, `payment`, `acquisition`, `opt_in`, `refund_method`), so
  existing columns and the scenario magnitudes are byte-identical. Reconciled
  `realism-guidance.md` (catalogs + mixes + a "these fields carry no signal" simplification
  note) and pinned tests (catalog membership, `weight_kg` bounds, brand∈category). The
  scenario-bearing items (`products.cost`, `orders.discount_amount`) stay in `TODO.md` for the
  scenario workflow. Status still **Needs investigation**: the enrichment added dimensions but
  no dedicated too-synthetic sweep has run.
- **2026-07-02 — `returns.item_condition` (high-leverage item 4).** Added arrival condition
  (`resellable` / `opened` / `damaged`), drawn per-row from a reason-keyed cumulative mix
  (child stream `condition`), and **re-keyed `restocked` off condition instead of `reason`
  directly** — closing the standing "restocked keyed only to reason" note (the reason→condition→
  restock chain replaces `_RESTOCK_P`). Measured: overall condition ≈ resellable 0.51 / damaged
  0.27 / opened 0.22; strong reason correlation (defect/transit-damage ~0.80–0.87 damaged,
  mind-change/fit ~0.75 resellable); restock-by-condition 0.97 / 0.50 / 0.04; mediated
  restock-by-reason ~0.85 (fit/mind-change) → ~0.63 (`not_as_described`) → ~0.08–0.15
  (defect/damage). Other columns byte-identical (`restock` child stream and count unchanged;
  only its per-row threshold moved from reason to condition). Reconciled `realism-guidance.md`
  (item_condition catalog + mix, restock-mediation line, removed the now-resolved simplification
  bullet, added a review query) and pinned tests (catalog membership, restock↔condition gap,
  damage-reason→damaged-condition).
