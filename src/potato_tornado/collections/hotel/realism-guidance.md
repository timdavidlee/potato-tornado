# Realism guidance — hotel

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **A stay implies an honoured reservation.** `stays` rows exist only for reservations with
  `status = 'honoured'`; `cancelled` / `no_show` reservations never produce a stay.
- **Booking arithmetic.** `check_in_date = booked_date + lead_days` with
  `lead_days ∈ [0, 240]`; `check_out_date = check_in_date + nights`; `nights ∈ [1, 21]`;
  `party_size ∈ [1, 6]`.
- **Stay drifts, doesn't teleport.** `stays.actual_nights` differs from the reservation's
  `nights` by at most −2 (early checkout) to +3 (extension), and is ≥ 1;
  `room_revenue = nightly_rate × actual_nights` exactly — where `stays.nightly_rate` is the
  calendar-adjusted **billed** rate (rack × season × weekend, see *Rate seasonality & weekend
  lift* below), not the flat rack rate in `room_types`.
- **Room revenue is net of tax; the wedge is separate.** `stays.room_revenue` is the net room
  charge — ADR / RevPAR read straight off it. `stays.taxes_fees ≥ 0` is a deterministic wedge
  on top: `room_revenue × VAT_country + actual_nights × city_tax_city`, so it's fully fixed by
  the property's country/city and the stay's revenue and nights (no RNG). It is never rolled
  into `room_revenue`.
- **Every property offers the full ladder.** `room_types` has all four types per property;
  the **rack** `room_types.nightly_rate = base × location_multiplier` with a 0.7× floor, so
  rates stay positive and keep the Standard < Deluxe < Suite < Penthouse ordering. (`stays`
  bills a calendar-adjusted rate off this rack — see *Rate seasonality & weekend lift* below —
  so `stays.nightly_rate` is not equal to `room_types.nightly_rate`.)
- **Occupancy is bounded.** `demand_forecast.actual_occupied_rooms ≤ total_rooms`; forecast
  is the actual perturbed by multiplicative noise (Normal(1.0, `sd`) with `sd`=0.09 on
  weekdays, 0.22 on weekends) and clipped to `[0, total_rooms]`; exactly one row per property
  per day across the config span.
- **Cancellations are dated, nothing else is.** `cancellation_date` is non-null **iff**
  `status = 'cancelled'` (`honoured` and `no_show` are null — a no-show never cancels); when
  present it falls in `[booked_date, check_in_date]`. This is the only nullable column.
- **Party composition reconstitutes.** `adults + children = party_size` on every
  reservation, with `adults ≥ 1` (`children` is capped at `party_size − 1`).
- **Geography rolls up from the city.** `properties.country` / `properties.region` are a
  deterministic lookup off `city` (via `CITY_GEO`); `star_rating ∈ {3, 4, 5}` and
  `opening_date` predates the generation window.
- **Room capacity is catalogued.** `room_types.max_occupancy` is a fixed lookup off
  `room_type` (Standard 2 → Deluxe 3 → Suite 4 → Penthouse 6), ascending with the ladder.
- **Per-class inventory reconciles.** `room_types.room_count` splits each property's
  `total_rooms` across its four classes and sums back to `total_rooms` exactly (deterministic
  largest-remainder apportionment, ≥1 of each class).
- **Service orders sit inside their stay.** Each `service_orders` row references a real
  `stay_id`, its `service_date` falls within the stay, `amount = unit_price × quantity`,
  `service_category` is the catalog rollup of `service`, and `unit_cost × quantity < amount`
  (every line keeps a positive margin).
- **Stay changes match the drift.** Each `stay_changes` row explains a non-zero gap
  between booked and realised nights: `nights_delta = actual_nights − booked_nights` is
  never 0, `change_type = 'early_checkout'` iff `nights_delta < 0` and `'extension'` iff
  `> 0`, and `actual_nights` agrees with the row's `stays` record. `fee > 0` in both cases
  (a flat one-night penalty for early checkout; a premium on the extra nights for
  extension) and is *separate* from `stays.room_revenue`, not a re-billing of it.
- **Upgrades move up the ladder.** Each `room_upgrades` row has `to_room_type` strictly
  above `from_room_type` in the Standard→Penthouse order; a Penthouse stay never appears as
  a `from_room_type` (it's already the top). `rate_delta > 0` is the property's rack-rate
  gap between the two classes, and `upgrade_fee < rate_delta × nights` always (the fee is a
  discounted slice of the gap, never the whole gap).
- **Cancellation notes render the reservation, leaking only the reason.** There is exactly
  one `cancellation_notes` row per **cancelled** reservation (none for `honoured` / `no_show`),
  `note_date` equals that reservation's `cancellation_date`, and `body` is free-form prose that
  *renders existing facts*: the "N days before arrival" it states equals
  `check_in_date − cancellation_date` exactly (so the timing is a faithful render, no answer
  leaked), and the `RES-` id it names is the row's `reservation_id`. The one fact that lives
  nowhere else is the cancellation **reason**, shipped as the withheld answer-key column
  `cancel_reason ∈ {rate_shopping, plans_changed, other}`; the bucket a rule-parser reads out of
  `body` equals `cancel_reason` for every row. See
  `scenarios/cancellation-notes-reveal-price-shopping.md`.
- **Referential integrity.** `reservations.property_id ∈ properties`,
  `stays.reservation_id ∈ reservations` (honoured),
  `cancellation_notes.reservation_id ∈ reservations` (cancelled), and `room_types` /
  `service_orders` / `room_upgrades` FKs resolve (`room_upgrades.stay_id ∈ stays`).

## Distributions & mixes (should look like the real world)

- **Channel mix.** Overall ota ≈0.45 (largest) / direct ≈0.33 / corporate ≈0.16 / walk_in
  ≈0.06 (the overall split is an emergent product of the room-type mix and the per-tier
  channel weights below), but keyed to room class: upper tiers (Suite/Penthouse) draw
  direct 0.55 / ota 0.22 /
  corporate 0.18 / walk_in 0.05, lower tiers direct 0.28 / ota 0.50 / corporate 0.16 /
  walk_in 0.06 — so direct is modal for the upper tiers. See
  `scenarios/ota-is-the-largest-channel.md`.
- **Room-type mix & rate ladder.** Standard 0.55 ($95) → Deluxe 0.28 ($145) → Suite 0.12
  ($260) → Penthouse 0.05 ($480), before the per-property location multiplier.
- **Inventory mix & occupancy by class.** Physical `room_count` is apportioned Standard 0.50
  / Deluxe 0.27 / Suite 0.15 / Penthouse 0.08 — deliberately more top-heavy than the booking
  mix above, so per-class utilization runs *down* the ladder: Standard ≈0.097 > Deluxe ≈0.092
  > Suite ≈0.068 > Penthouse ≈0.058. See `scenarios/premium-rooms-run-cooler.md`.
- **Reservation status.** Overall honoured ≈0.85 / cancelled ≈0.12 / no_show ≈0.035. The
  base mix is keyed to channel (per-channel honoured/cancelled/no_show — direct 0.88/0.09/0.03,
  ota 0.73/0.21/0.06, corporate 0.85/0.12/0.03, walk_in 0.98/0.02/0.00), and the drop-off
  (cancel + no_show) mass is then scaled by `rate_plan` (`RATE_PLAN_CANCEL_MULT`), so the
  observed per-channel drop-off softens to ota ≈0.22 ≫ corporate ≈0.14 > direct ≈0.10 ≫
  walk_in ≈0.02. See `scenarios/reservation-funnel.md`.
- **Rate plan.** The RM axis, orthogonal to channel and keyed to it: overall BAR ≈0.37 /
  Advance-Purchase ≈0.29 / Package ≈0.19 / Corporate-negotiated ≈0.15 (corporate books the
  negotiated rate ≈0.75 of the time, walk_in pays BAR ≈0.78). Cancellation depends on it —
  non-refundable Advance-Purchase drops off ≈0.07 vs flexible BAR ≈0.23, ≈3× less. See
  `scenarios/non-refundable-rates-cancel-less.md`.
- **Cancellation timing.** For cancelled bookings, `cancellation_date = booked_date + f ×
  lead_days` with the window fraction `f ~ Beta(a, b)` keyed to rate plan: flexible BAR
  cancels late (`f` ≈0.61), non-refundable Advance-Purchase early (`f` ≈0.23). As days before
  arrival that's Advance-Purchase ≈24 vs BAR ≈10; ~12% of bookings are cancelled. See
  `scenarios/cancellations-land-late-for-flexible-rates.md`.
- **Cancellation reason mix (free-text).** `cancellation_notes.cancel_reason` is drawn
  conditional on the reservation's `rate_plan` (`rate_shopping` / `plans_changed` / `other`):
  flexible BAR skews to price-shopping (`rate_shopping` ≈0.63, dominant), non-refundable
  Advance-Purchase to a genuine plan change (`plans_changed` ≈0.67, `rate_shopping` ≈0.17),
  with Package (`rate_shopping` ≈0.46) and Corporate-negotiated (`plans_changed` ≈0.54) between;
  overall ≈`rate_shopping 0.50 / plans_changed 0.34 / other 0.16`. So price-shopping is a
  refundable-rate phenomenon — legible only after parsing the note. See
  `scenarios/cancellation-notes-reveal-price-shopping.md`.
- **Booking volume & occupancy.** ~24,000 reservations across the 3-year window, assigned to
  properties **in proportion to room count**, so occupancy scales with size instead of sitting
  flat: small (~60-room) properties run ≈5 occupied rooms/day, large (~210-room) ones ≈15
  (overall mean ≈10, peaks ~30, always under capacity), and utilization lands at a comparable
  ≈7–8% across every property. The double-digit occupancy at the larger properties is
  deliberate: it's what lets the forecast's ~10% MAPE show through integer rounding — see
  `scenarios/forecast-tracks-actual-with-error.md`.
- **Lead time.** Lognormal with a per-channel `(median, sigma)`, right-skewed out to the
  240-day cap. Overall median ≈13 / mean ≈24 / p95 ≈84, but the tail is fattest for the OTA
  and near-zero for walk_in: ota (24, 1.0), direct (12, 0.85), corporate (8, 0.8), walk_in
  (1, 0.6). See `scenarios/lead-time-is-right-skewed.md`.
- **Length & party.** Both are `Poisson(λ)+1` with `λ` keyed to a segment rather than flat
  across the table. `nights` λ is keyed to channel — business channels stay shorter than
  leisure: corporate/walk_in ≈2.6 nights, direct ≈3.3, ota ≈3.6 (overall mean ≈3.3), capped
  at 21. `party_size` λ is keyed to room class — larger rooms draw larger parties: Standard
  ≈2.1, Deluxe ≈2.3, Suite ≈2.7, Penthouse ≈2.8 (overall mean ≈2.3), capped at 6.
- **Party composition.** `party_size` splits into `adults + children`; `children ~
  Poisson(λ)` capped at `party_size − 1`, with `λ` keyed to market segment — leisure ≈0.37
  children/party, group ≈0.24, business ≈0.03 (near-childless). So most business rooms are
  adult-only and families concentrate in leisure/group.
- **Market segment.** The demand-side axis (`leisure` / `business` / `group`), keyed to
  channel and orthogonal to it: corporate is ≈0.78 business, the OTA ≈0.80 leisure,
  direct/walk_in in between; group is a ≈0.10 slice everywhere. The overall split is an
  emergent product of the channel mix and these per-channel weights: leisure ≈0.63 /
  business ≈0.27 / group ≈0.10.
- **Guest origin.** `guest_country` is the property's own country with probability ≈0.58,
  else a weighted international feeder market (UK, Germany, France, US, …); the observed
  domestic share lands ≈0.61 (a little above 0.58 because a feeder draw can coincide with the
  property's country).
- **Payment method.** `stays.payment_method` (`card` / `cash` / `corporate_ar`) keyed to
  channel: corporate settles ≈0.68 on accounts-receivable, the OTA is ≈0.93 card, walk_in
  carries the most cash (≈0.28); card dominates overall.
- **Ancillary categories & cost.** `service_category` rolls the nine services into F&B /
  Wellness / Connectivity / Parking (F&B is the largest by volume). `unit_cost` is the
  category's cost-fraction of price (F&B 0.34, Wellness 0.22, Parking 0.12, Connectivity
  0.06) times a per-line jitter, so gross margin varies by category and line — never a
  constant ratio, always positive.
- **Property attributes.** Six properties carry a `star_rating` (3–5★, weighted toward 4★),
  an `opening_date` 2–15 years before the window (maturity cohorts), and a
  `city → country → region` rollup (Iberia vs. Western Europe).
- **Ancillary spend scales with stay.** Service-order count ~ Poisson(0.9 × nights) — longer
  stays accrue more entries. The catalog mixes discretionary spend (Breakfast, Spa, Dining,
  Room Service, Minibar, Laundry) with recurring stay fees (Internet, Television, Parking).
  Menu demand is **popularity-weighted, not uniform**: breakfast ≈0.20 / internet ≈0.16 /
  parking ≈0.14 are everyday buys, spa ≈0.04 / laundry ≈0.05 occasional. Line `quantity` is
  right-skewed — 1 (≈0.70) / 2 (≈0.24) / 3 (≈0.06).
- **Upgrades are a discounted upsell, concentrated in direct bookings.** ~15% of eligible
  stays upgrade (Penthouse stays excluded), but the rate is keyed to the booking channel:
  direct 0.25 / walk_in 0.15 / corporate 0.14 / ota 0.08 — so the upsell is a direct-channel
  play. Most jump one rung (80%), occasionally two; the fee is 55–80% of the rack-rate delta
  (mean ≈0.68) regardless of channel. See
  `scenarios/upgrades-concentrate-in-direct-bookings.md`.
- **Stays extend more than they shorten.** ~20% of stays are amended; of those, extensions
  outnumber early checkouts ~1.7:1. Early checkouts cut 1–2 nights (flat one-night penalty);
  extensions add 1–3 nights (10–25% premium). See
  `scenarios/extensions-outnumber-early-checkouts.md`.
- **Review scores.** Post-stay `review_score ∈ [1, 5]`, `Normal(μ, 0.8)` rounded and clipped,
  overall mean ≈4.1 and left-skewed to 4s/5s. `μ` keys off the stay outcome (early checkout
  −1.1, extension +0.25) and channel (direct +0.15, ota −0.3), so early_checkout stays average
  ≈3.1 vs ≈4.1 unchanged, and ota ≈3.9 < direct ≈4.3. See
  `scenarios/early-checkouts-score-lower.md`.
- **Tax wedge.** `taxes_fees` runs at an effective ≈0.096 of `room_revenue` overall, but the
  rate is geography-keyed: reduced accommodation VAT (Portugal 6%, Spain/France/Italy 10%) plus
  a flat per-room-night city tax (Lisbon/Porto €2, Lyon €1.5, Turin €1.4, Spanish cities €0).
  So the effective load runs Portugal ≈0.072 < Spain ≈0.100 < Italy ≈0.109 < France ≈0.110,
  and by region Iberia ≈0.085 < Western Europe ≈0.109. See
  `scenarios/tax-load-lighter-in-iberia.md`.
- **Location pricing.** Per-property nightly-rate multiplier ~ Normal(1.0, 0.12).
- **Rate seasonality & weekend lift.** `stays.nightly_rate` is the **billed** rate, not the flat
  rack: the room's rack rate (`room_types.nightly_rate`) times a day-of-year summer season factor
  (cosine, amplitude `_RATE_SEASON_AMP` = 0.15, peak mid-July at `_RATE_PEAK_DOY` = 196 — matching
  `reservations._PEAK_DOY` so price peaks with demand, giving a peak-day:trough-day rate of
  `(1 + 0.15)/(1 − 0.15) ≈ 1.35×`) and a weekend-arrival lift (`_RATE_WEEKEND_LIFT` = 1.10 for
  Fri–Sun arrivals, `weekday() ≥ 4`). Both are pure deterministic (no RNG), so they shift no other
  column's draws; `room_revenue = nightly_rate × actual_nights` bills at this calendar-adjusted
  rate, and `taxes_fees` derives from that `room_revenue`. So within one (property, room_class) the
  billed rate spreads across many values over the calendar instead of sitting at a single rack rate.
- **Seasonal arrivals.** Check-ins follow a repeating annual season with a summer peak and
  winter trough — a day-of-year cosine (amplitude 0.23, peak mid-July) gives a peak-day:
  trough-day ratio of `(1 + 0.23)/(1 − 0.23) ≈ 1.6×`; averaged into calendar months the
  observed summer:winter ratio is ≈1.5×, recurring across the ~3-year window;
  `booked_date = check_in − lead_days` so the peak lands on arrivals. See
  `scenarios/check-ins-peak-in-summer.md`.

## Deliberate simplifications (intended — do not "fix")

- Six properties, one per city, capped at the `CITIES` catalog length.
- The forecast is `actual × noise` with **no systematic bias** (it tracks actual by
  construction, only the error *magnitude* varies by weekday/weekend — `sd` 0.09/0.22) and no
  real forecasting model — see `scenarios/forecast-tracks-actual-with-error.md`. Making the
  error band **covary with demand** (a bigger APE at low occupancy) was investigated
  (2026-07-11) and is **un-pinnable here**, so the flat weekday/weekend band stays deliberate:
  occupancy is a near-uniform ≈8% everywhere, so an `occ_frac`-scaled `sd` can't manufacture a
  low-vs-high-occupancy differential, and integer rounding of `forecast_occupied_rooms` already
  damps low-occupancy APE the *opposite* way. No demand-sensitivity coefficient flips low-occ
  APE above high-occ APE while keeping the pinned
  `test_forecast_tracks_actual_within_about_ten_percent` green (the full-scale MAPE ceiling is
  0.16; the `sd` ≈0.3+ needed to move the signal triples MAPE past it).
- Room type is drawn independently; channel depends on room class; lead time depends on
  channel (the OTA lead-time tail in `scenarios/lead-time-is-right-skewed.md`); and status
  depends on both channel (the OTA drop-off in `scenarios/reservation-funnel.md`) and
  rate_plan (the non-refundable stickiness in `scenarios/non-refundable-rates-cancel-less.md`).
  Status is not otherwise keyed to room class, lead time, or season.
- Guests are not deduplicated: every reservation is a fresh name, so there is no
  repeat-guest / loyalty signal.
- Recurring fees (Internet, Television, Parking) are modeled as discretionary
  `service_orders` lines drawn ~Poisson(nights), not mandatory per-night folio charges — so
  a stay may show zero or several, rather than exactly one per night.
- Bookings aren't constrained by physical room inventory; only `demand_forecast` occupancy is
  capped at `total_rooms`. `demand_forecast` stays **property-level**, not per class, even
  though `room_types.room_count` now makes per-(property, class, day) occupancy derivable from
  `stays` — the by-class occupancy signal lives in the data, just not in the forecast grid.
- **Check-outs spill past the window; `stays` are deliberately not right-censored.**
  `stays.actual_check_out = actual_check_in + actual_nights` can land after the config
  `end_date` when a late-window arrival's stay runs over — the window bounds the *anchor*
  event (the booking/arrival), not the completed stay. This is an **intentional divergence**
  from `labor` (project completions) and `streaming` (subscription cancellations), which now
  right-censor their lifecycle end-dates: those carry an active-status flag and a nullable
  end-date, so censoring an unresolved future is faithful. A hotel `stays` row is a
  *completed-revenue* record — `room_revenue` / `taxes_fees` are already earned and the length
  drift is already realised — so truncating or nulling its check-out would fabricate
  early-checkouts and break the revenue identities for no analytical gain. Hotel is therefore
  the documented exception the `labor` / `streaming` rubrics point back to.
- **Arrivals have no day-of-week structure.** Check-ins are weighted by day-of-*year* (the
  summer season) but drawn flat across the day of the week — real hotels see a weekend-leisure /
  midweek-business arrival rhythm this data omits. (A candidate to promote into a new scenario.)
- **Upgrades are always dated on the arrival day.** Every `room_upgrades.upgrade_date` equals
  the stay's check-in — the upsell is modeled as a front-desk sale at check-in, so there is no
  at-booking or mid-stay upgrade timing. The fee still bills over the full stay `nights`.
- **`star_rating` is independent of rate.** The per-property star rating is drawn on its own
  and does *not* feed `nightly_rate`, so ADR won't correlate with stars. (A star-rating rate
  premium is a strong candidate to promote into a new scenario — deliberately not wired here.)
- **`review_score` is independent of property / star_rating.** `μ` keys only off the stay
  outcome (early checkout / extension) and channel, not the property or its stars, so mean
  review is flat across properties (≈4.07–4.11) and across the 3★/4★ split — the per-stay
  `Normal(μ, 0.8)` scatter is real, but there is no property or star-quality effect. (A
  star-rating review premium is a candidate to promote into a new scenario, alongside the
  star-rating rate premium above — deliberately not wired here.)
- **`party_size` isn't capped by the room's `max_occupancy`.** Party size is drawn from room
  *class* λ, not the room's rated capacity, so a minority of parties exceed `max_occupancy`
  (e.g. a 3-guest Standard booking) — an over-occupancy / upsell hook to slice on, not a bug.
- **No year-over-year trend.** Arrivals are drawn from a day-of-*year* season only, with no
  multi-year growth or decline term, so booking volume is flat across the window's three
  calendar years (each carries ≈1/3 of check-ins) apart from the summer/winter cycle that
  repeats identically each year. Real hotels grow or shrink year to year; here the level holds.
  (A YoY demand trend is a candidate to promote into a new scenario — deliberately not wired.)
- **The class rate ladder is identical across properties.** `nightly_rate = base ×
  location_multiplier` applies **one** per-property multiplier to all four classes, so the
  *relative* ladder (e.g. Deluxe/Standard ≈1.53, Penthouse/Standard ≈5.05) is the same at every
  property — properties differ in overall price level, not in how steeply they price the ladder.
  Real chains vary their class-pricing power by property. (Per-property class-pricing spread is
  a candidate to promote into a new scenario — deliberately not wired here.)
- **Service `amount` is whole-dollar.** The `service_orders` menu carries fixed whole-dollar
  unit prices (Breakfast $18, Spa $75, …), so `amount = unit_price × quantity` takes only ~25
  distinct round values with no cents — a fixed price list, not a synthetic lattice. (Per-line
  `unit_cost` *does* carry jittered cents; the guest-facing `amount` is deliberately clean.)

## How to review

```sql
-- OTA is the largest channel (≈ 0.45)
select channel, count(*) * 1.0 / sum(count(*)) over () as share
from reservations group by channel order by share desc;    -- ota on top

-- stays exist only for honoured reservations: expect 0
select count(*) from stays s
join reservations r using (reservation_id)
where r.status <> 'honoured';                               -- expect 0

-- occupancy never exceeds capacity: expect 0
select count(*) from demand_forecast f
join properties p using (property_id)
where f.actual_occupied_rooms > p.total_rooms;              -- expect 0

-- room revenue reconciles: expect 0 mismatches
select count(*) from stays
where round(nightly_rate * actual_nights, 2) <> room_revenue;  -- expect 0

-- check-ins spread evenly across the three calendar years (flat YoY, no growth trend)
select extract(year from check_in_date) as yr,
       count(*) * 1.0 / sum(count(*)) over () as share
from reservations group by yr order by yr;                     -- each ≈ 0.33
```
