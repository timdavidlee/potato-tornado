# Hotel — field-enrichment TODO

Candidate columns to add to the existing `hotel` tables for analytics richness. Ordered:
**quick wins first** (plain realism enrichment — new dimensions to slice by), then the
**high-leverage items** (each unlocks a whole analysis domain; several carry a teachable
subset signal, so they go through `/scenario:draft-or-propose`, not the realism command).

**Status:** the field-enrichment backlog is **fully done** — all 10 quick wins, all 4
high-leverage items, and the ADR / RevPAR revenue split (see [Done](#adr--revpar-revenue-split--done)).
Each was implemented with name-keyed child streams (or, for the tax wedge, a pure deterministic
derivation) so existing columns are unshifted, reconciled in `realism-guidance.md`, and pinned
with tests in `tests/collections/hotel/test_hotel.py`. Five items planted a scenario doc. No
open items remain; the completed work is kept below as an implementation record.

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See
[collections/CLAUDE.md](../CLAUDE.md).

## ADR / RevPAR revenue split — done

- [x] Added `stays.taxes_fees` — the tax wedge on top of the net room charge, a *pure
      deterministic derivation* (no RNG): `room_revenue × VAT_country + actual_nights ×
      city_tax_city` (`VAT_RATE_BY_COUNTRY`, `CITY_TAX_PER_NIGHT`). `room_revenue` stays **net
      of tax**, so ADR / RevPAR read straight off it and (with #4's `room_count`) the industry
      KPIs (ADR, RevPAR, TRevPAR) are all computable.
- **Scenario:** planted **the effective tax load is lighter across Iberia** —
      `scenarios/tax-load-lighter-in-iberia.md` (effective rate Portugal ≈0.072 < Spain ≈0.100
      < Italy ≈0.109 < France ≈0.110; Iberia ≈0.085 vs Western Europe ≈0.109, overall ≈0.096).
      Gives the `country` / `region` rollup a revenue payoff. Realism-guidance reconciled;
      pinned with tests.

## Quick wins (realism enrichment) — done

All implemented in one batch (constants + `tables/` builders via name-keyed child streams so
existing columns' draws are unchanged), reconciled in `realism-guidance.md`, and pinned with
tests in `tests/collections/hotel/test_hotel.py`.

- [x] **`reservations.market_segment`** — leisure / business / group, keyed to channel
      (`SEGMENT_BY_CHANNEL`); corporate ≈0.78 business, OTA ≈0.80 leisure.
- [x] **`reservations.adults` / `reservations.children`** — `children ~ Poisson(λ_segment)`
      capped at `party_size − 1`; `adults = party_size − children` (sum invariant holds).
- [x] **`reservations.guest_country`** — property country w.p. ≈0.58 else weighted
      international feeder (`GUEST_SOURCE_COUNTRIES`); observed domestic share ≈0.61.
- [x] **`service_orders.service_category`** — F&B / Wellness / Connectivity / Parking; added
      as the 4th element of the `SERVICES` catalog tuple, looked up per line.
- [x] **`service_orders.unit_cost`** — `price × COST_FRACTION_BY_CATEGORY × per-line jitter`;
      margin varies by category/line, always positive.
- [x] **`stays.payment_method`** — card / cash / corporate-AR, keyed to channel
      (`PAYMENT_BY_CHANNEL`); corporate ≈0.68 AR, OTA ≈0.93 card.
- [x] **`properties.star_rating`** — 3–5★ (weighted to 4★). Drawn independently of rate — a
      star↔rate premium is left as a candidate scenario (see realism-guidance simplifications).
- [x] **`properties.country` / `properties.region`** — `city → country → region` rollup via
      `CITY_GEO` (Iberia vs. Western Europe).
- [x] **`properties.opening_date`** — 2–15 years before the window → maturity cohorts.
- [x] **`room_types.max_occupancy`** — fixed lookup off `room_type` (2/3/4/6). `party_size`
      may exceed it (deliberate over-occupancy / upsell hook).

## High-leverage additions

### 1. `reservations.rate_plan` — done

- [x] Added `BAR` / `Advance-Purchase` (non-refundable) / `Corporate-negotiated` / `Package`,
      keyed to channel (`RATE_PLAN_BY_CHANNEL`). Status now scales the channel drop-off by
      `RATE_PLAN_CANCEL_MULT`, so cancellation depends on rate plan as well as channel.
- **Unlocks:** cancellation behavior by rate plan (ADR-by-rate-plan awaits a rate discount,
      see Later).
- **Scenario:** planted **non-refundable rates cancel less** —
      `scenarios/non-refundable-rates-cancel-less.md` (Advance-Purchase ≈0.07 drop-off vs BAR
      ≈0.23). Funnel scenario + realism-guidance reconciled; pinned with tests.

### 2. `reservations.cancellation_date` — done

- [x] Nullable `Date`, populated **only** for `cancelled` rows (honoured *and* no_show are
      null — a no-show never cancels), at `booked_date + f × lead_days`. The collection's
      first NULL column (~88% null).
- **Unlocks:** cancellation curves, lead-to-cancel, revenue-at-risk N days out, NULL handling.
- **Scenario:** planted **flexible rates cancel late, non-refundable early** —
      `scenarios/cancellations-land-late-for-flexible-rates.md` (window fraction BAR ≈0.61 vs
      Advance-Purchase ≈0.23; ≈24 vs ≈10 days before arrival). Realism-guidance reconciled;
      pinned with tests.

### 3. `stays.review_score` — done

- [x] Post-stay 1-5 rating, `Normal(μ, 0.8)` rounded/clipped, `μ` keyed to stay outcome and
      channel. Overall mean ≈4.1, left-skewed. The collection's outcome variable.
- **Unlocks:** satisfaction by segment / property / channel / after an early-checkout.
- **Scenario:** planted **early checkouts score lower** —
      `scenarios/early-checkouts-score-lower.md` (early_checkout ≈3.1 vs ≈4.1 unchanged; ota
      ≈3.9 < direct ≈4.3). Realism-guidance reconciled; pinned with tests.

### 4. `room_types.room_count` (per-class inventory) — done

- [x] Rooms per class per property, apportioned from `total_rooms` (largest-remainder, sums
      exactly, ≥1 each). Inventory mix (Standard 0.50 / Deluxe 0.27 / Suite 0.15 / Penthouse
      0.08) is deliberately more top-heavy than the booking mix.
- **Unlocks:** occupancy / availability / **RevPAR by room class**. (`demand_forecast` kept
      property-level — per-(property, class, day) occupancy is still derivable from `stays`.)
- **Scenario:** planted **premium rooms run cooler** —
      `scenarios/premium-rooms-run-cooler.md` (utilization Standard ≈0.097 down to Penthouse
      ≈0.058). Realism-guidance reconciled; pinned with tests.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items. Most are documented candidates to *promote into scenarios*.

- [ ] **No weekday/weekend or seasonal rate variation.** Rates are flat by calendar (a
      documented simplification); a rate-by-day-of-week series reads implausibly flat — the
      strongest realism-flavoured candidate.
- [ ] **Forecast error band is flat across segments.** Documented as not varying by weekend; a
      candidate to make error covary with demand.
- [ ] **Star-rating review premium / YoY demand trend not wired.** Both are documented
      candidates to promote into scenarios (`/scenario:draft-or-propose`); today the cross-tabs
      read flat.
