# Realism guidance — streaming

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** `subscriptions.subscriber_id ∈ subscribers`,
  `subscriptions.plan ∈ plans.plan`, `rentals.subscriber_id ∈ subscribers`,
  `rentals.title_id ∈ titles`, `titles.lead_actor ∈ actors.actor` (both the
  `titles` builder and the `actors` catalogue derive from the same `CELEBRITIES`
  source of truth, so this holds by construction), and `subscribers.region` /
  `title_availability.region ∈ regions.region`.
- **One subscription per subscriber.** Exactly one `subscriptions` row per subscriber, its
  `start_date` equal to the subscriber's `signup_date`.
- **Lifecycle dates.** `status = 'cancelled'` rows have a non-null `end_date` strictly after
  `start_date`; `status = 'active'` rows have a null `end_date`.
- **Anchor-event dates fall within the window.** `subscribers.signup_date` and
  `rentals.rented_date` lie in `[start_date, end_date)`. `titles.release_date` may predate the
  window (back catalogue — drawn from 5 years before `start_date`), and a cancelled
  subscription's derived `end_date` may fall *after* it (see Deliberate simplifications).
- **Billing cadence.** `subscriptions.billing_cycle ∈ {monthly, annual}`.
- **Cancel reason mirrors status.** `subscriptions.cancel_reason` is non-null **exactly** when
  `status = 'cancelled'` (null for active), and non-null values come from the fixed set
  `{price, content, technical, competitor, other}`. No third state.
- **Acquisition channel is from the catalog.** `subscribers.acquisition_channel ∈
  ACQUISITION_CHANNELS` (`{organic, paid_search, social, referral, partner}`).
- **Ratings are bounded.** `titles.avg_rating ∈ [1.0, 10.0]`; `rentals.rating` is either null
  (unrated) or an integer in `{1, 2, 3, 4, 5}`.
- **Every title is licensed somewhere.** Each `titles.title_id` appears in
  `title_availability` for at least one region; each `(title_id, region)` pair is unique.
- **Rentals hit premium titles.** Every `rentals.title_id` references a title with
  `is_premium = true` (unless a tiny scale produced no premium titles, in which case rentals
  fall back to the region's — then the full — catalogue).
- **Rentals are locally licensed.** Every rental's title is licensed in the renter's region:
  the title appears in `title_availability` for `subscribers.region`. A three-table anti-join
  (`rentals` → `subscribers.region` → `title_availability`) for a title not licensed in the
  renter's region returns 0 rows.
- **Rental price is a known price point.** `rentals.price ∈ {4.99, 6.99, 19.99}`.
- **Rentals fall on/after release.** `rentals.rented_date >= titles.release_date` for the
  rented title (you can't rent a title before it exists) and stays within the window — the date
  is drawn as a fraction of `[max(release_date, start_date), end_date)`, so a rental never
  predates its title.
- **Plan attributes are a fixed function of tier.** From `PLANS`: Basic 1 stream / `SD` / ad-supported, Standard 2 / `HD` / ad-free, Premium 4 / `UHD` / ad-free — so `plans.max_streams ∈ {1, 2, 4}`, `plans.video_quality ∈ {SD, HD, UHD}`, and `plans.ad_supported` is true only for Basic. No jitter.
- **Every region has a currency.** `regions.currency` is the market's ISO code from `REGIONS` (US USD, GB GBP, DE EUR, BR BRL, IN INR, JP JPY) — exactly one per region, never null.
- **Title runtime is positive.** `titles.runtime_minutes > 0` (a clamped-normal keyed on `kind`, floored at 5 minutes), and `titles.maturity_rating ∈ MATURITY_RATINGS` (`{G, PG, PG-13, R, TV-MA}`).
- **Categorical dimensions are from their catalogs.** `subscribers.device_platform ∈ DEVICE_PLATFORMS` (`{ios, android, web, smart_tv, roku}`) and `rentals.payment_method ∈ PAYMENT_METHODS` (`{card, paypal, gift_card, wallet}`).
- **Title names follow the figure-in-off-genre pattern.** Every `titles.name` is a
  `<celebrity> in <show>` / `<celebrity>'s <show>` string where the celebrity is drawn from
  the `CELEBRITIES` catalogue and the show genre is never that celebrity's `home_genre`.
  Series names carry an `Episode N` / `Season N` suffix; films do not. Names are *not*
  guaranteed unique — `title_id` is the key.
- **`lead_actor` / `genre` match the name.** `titles.lead_actor` is the figure named at the
  start of `titles.name`, `titles.genre ∈ GENRES`, and `genre` is never the `lead_actor`'s
  `home_genre` (the off-genre invariant, made queryable).

## Distributions & mixes (should look like the real world)

- **Plan mix.** Overall Basic ≈0.28 / Standard ≈0.46 (largest) / Premium ≈0.26, but keyed to
  region: the US draws Basic 0.18 / Standard 0.34 / Premium 0.48 (Premium modal), every other
  region draws Basic 0.34 / Standard 0.55 / Premium 0.11. See
  `scenarios/standard-is-the-most-popular-plan.md`.
- **Subscription status.** Overall ≈0.79 active / ≈0.21 cancelled — but churn is **not
  flat**: each subscriber's cancel probability is `_BASE_CANCEL_RATE` (0.20) scaled by an
  acquisition-channel multiplier and a billing-cadence multiplier, clipped to [0, 0.95]. So
  cancelled-rate ladders from ≈0.10 (organic/referral) to ≈0.38 (paid_search), and ≈0.25
  monthly vs ≈0.08 annual. See `scenarios/paid-channels-churn-faster.md` and
  `scenarios/annual-plans-retain-better.md`.
- **Tenure.** Whole months ~ Poisson(λ)+1, capped at 24 (right-skewed), where λ = 6 scaled by
  the same channel/billing multipliers in the *opposite* direction — paid + monthly run short,
  organic + annual long. Cancelled-monthly mean is stable ≈5.6 months; cancelled-annual is a
  small, noisy sub-sample (few subscribers are both annual *and* cancelled) that runs ≈8.6 at
  the seed=7/scale=0.5 test config but centres nearer ~10 months at full scale (annual/monthly
  tenure ratio ~1.8×). Only cancelled rows expose tenure via `end_date`.
- **Acquisition channel mix.** organic 0.34 / paid_search 0.24 / social 0.18 / referral 0.14 /
  partner 0.10 — the acquisition dimension the churn signal cuts by.
- **Billing cadence mix.** monthly ≈0.80 / annual ≈0.20.
- **Cancel reason mix.** Base (per cancelled row) price 0.28 / content 0.22 / technical 0.20 /
  competitor 0.15 / other 0.15, then reweighted by segment: `content` ×2.6 in narrow-catalogue
  regions (JP/IN) and `price` ×2.2 on the Basic tier. Net: `content` ≈0.39 of JP/IN
  cancellations vs ≈0.16 elsewhere; `price` ≈0.44 of Basic cancellations vs ≈0.28 on higher
  tiers. See `scenarios/cancellation-reasons-vary-by-segment.md`.
- **Title quality score.** `avg_rating` ~ Normal keyed on `is_premium` (premium mean 7.5,
  non-premium 6.3, sd 1.2) clamped to [1, 10] — premium ≈7.5 vs ≈6.3. See
  `scenarios/premium-titles-score-higher.md`.
- **Rental rating.** ~40% of rentals are rated (the rest null); the rated score (1–5) is keyed
  on the price tier — mean ≈4.0 at $4.99/$6.99 but ≈2.8 at the rare $19.99 tier. See
  `scenarios/premium-rentals-rate-lower.md`.
- **Content mix.** series 0.60 / film 0.40; ~25% of titles are premium-rental eligible.
- **Region subscriber mix.** US 0.34 / BR 0.16 / IN 0.16 / GB 0.14 / DE 0.12 / JP 0.08.
- **Catalogue density by region.** Per-title licensing probability: US 0.85 / GB 0.60 /
  DE 0.55 / BR 0.50 / IN 0.45 / JP 0.30 — so catalogue size runs US (~85%+ of titles) down
  to JP (~30%). See `scenarios/catalog-size-varies-by-region.md`.
- **Rental price mix.** The PVOD ladder is skewed, not uniform: 4.99 ≈0.42 / 6.99 ≈0.45
  (modal) / 19.99 ≈0.13 — the two cheaper tiers carry the volume and the day-and-date premium
  release stays rare.
- **Runtime by kind.** `runtime_minutes` is feature-length for films (≈110±20 min) and a
  single episode for series (≈45±10 min), so films run ~2.5× a series row. Floored at 5.
- **Maturity mix.** G ≈0.08 / PG ≈0.20 / PG-13 ≈0.34 (modal) / R ≈0.20 / TV-MA ≈0.18 — flat
  across the catalogue (drawn independently of genre/kind).
- **Device mix.** android ≈0.26 / ios ≈0.24 / smart_tv ≈0.22 / web ≈0.18 / roku ≈0.10 —
  mobile-heavy with a solid TV share, flat across regions and plans.
- **Payment mix.** card ≈0.62 (dominant) / paypal ≈0.20 / wallet ≈0.10 / gift_card ≈0.08 —
  flat across rentals (independent of price and region).

## Deliberate simplifications (intentional — do not "fix")

- **Region is fixed per subscriber.** A subscriber never changes market and there is no
  travel/VPN notion; the licensing check is purely `subscribers.region`.
- **Licensing is independent per region.** A title's presence in one market is drawn
  independently of another (no "worldwide vs. regional-exclusive" tiers), apart from the
  orphan rule that puts any un-licensed title into the widest market.
- **Parody title names.** `titles.name` deliberately drops a real public figure into an
  absurd off-genre show ("Tom Cruise in Big Mama's Family") for comedic effect. The figures
  are public; the shows are fictional. The off-genre mismatch is the point — do not "correct"
  it toward the figure's real work.
- **No viewing/watch events.** Watch sessions and a show → season → episode hierarchy are the
  intended expansion; only the subscription and rental revenue streams exist today.
  `titles.avg_rating` and `rentals.rating` are standalone quality/satisfaction *scores* — there
  is no underlying rating/watch event log they roll up from.
- **Premium eligibility is independent of release recency.** `titles.is_premium` is a flat
  Bernoulli(0.25) drawn independently of `release_date`, so a years-old back-catalogue title is
  as likely to be rental-eligible as a brand-new one — even though "premium / day-and-date"
  connotes a recent release. Premium share by recency is flat (≈0.25 either side of the median
  release date). Tilting `is_premium` toward recent releases is a candidate future scenario
  (premium titles skew new), not a realism fix — don't plant it here.
- **Flat lifecycle.** One subscription per account, no plan upgrades/downgrades, and a
  subscriber's plan never changes. Churn is no longer flat — it varies by acquisition channel
  and billing cadence (planted; see the churn scenarios) — but it does **not** depend on plan
  or region, and `cancel_reason` is the only lifecycle field keyed off plan/region.
- **Rentals are independent of tenure.** A subscriber can rent on any date in the window,
  regardless of whether their subscription was active then. Tightening rentals to fall
  within an active subscription window is a candidate future invariant.
- **Cancellations can settle after the window.** A cancelled subscription's `end_date` is
  `signup_date + tenure` and is *not* right-censored at `end_date`, so ~15–17% of
  cancellations (long tenures on late signups) resolve past the window end — up to ~14 months
  beyond. This mirrors the house convention for derived end-dates (hotel check-outs and labor
  project completions likewise spill past `end_date`): the window bounds the *anchor* event
  (signup), not the lifecycle that plays out after it. Right-censoring is a candidate future
  refinement, not a realism fix.
- **Rentals spread uniformly across subscribers.** The renter of each rental is drawn
  uniformly, so there is no "heavy renter" concentration (rentals/subscriber ≈ Poisson-ish,
  max a handful). Concentrating rentals in a whale minority is a candidate future scenario,
  not a realism fix.
- **Rental price is per-transaction, not a title attribute.** `rentals.price` is an
  independent weighted draw on every rental, so the *same* title can be rented at $4.99 and
  $19.99 in the same period — price does not attach to the title, nor decay from a day-and-date
  $19.99 toward catalogue pricing as a release ages. A title×time price ladder (new releases
  command the premium tier, older ones drop) is a candidate future scenario, not a realism fix.
- **Genre is near-uniform across titles.** Each title is a random figure dropped into a
  random *off-genre* show, so the eight show genres come out roughly even (each ≈0.09–0.17)
  rather than following a real catalogue's skew. The uniform draw is a by-product of the
  parody device, not a distribution to "fix".
- **The new descriptive dimensions are drawn independently.** `subscribers.device_platform`,
  `titles.runtime_minutes` (keyed only on `kind`), `titles.maturity_rating`, and
  `rentals.payment_method` are flat draws with no cross-field correlation — device does not vary
  by region or plan, maturity does not vary by genre, and payment method does not vary by price.
  They are realism dimensions to slice by, not planted signals; a device-mix-by-region or
  maturity-by-genre skew would be a future scenario, not a realism fix.
