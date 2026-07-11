# streaming — field-enrichment TODO

Candidate columns to add to the existing `streaming` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

## Status

**14 of 14 items shipped.** All 8 quick wins (realism enrichment) and all 5 high-leverage
items (scenario-bearing) are implemented, with reconciled `realism-guidance.md`, pinned
invariant/magnitude tests, and — for the high-leverage five — scenario docs. Determinism was
preserved throughout (every new random draw uses a dedicated `ctx.rng.child(...)` stream, so
existing columns are byte-identical). **Item 6 (`subscriptions.mrr`)** shipped 2026-07-11 as a
pure derivation (no RNG) — the enrichment backlog is now complete.

Current live schema after enrichment (seed=7, scale=0.3), added columns in **bold**:

- `plans` — plan, monthly_price, **max_streams**, **video_quality**, **ad_supported**
- `regions` — region, name, **currency**
- `actors` — actor, home_genre *(unchanged)*
- `titles` — title_id, name, lead_actor, genre, kind, **runtime_minutes**, **maturity_rating**,
  release_date, is_premium, **avg_rating**
- `title_availability` — title_id, region *(unchanged)*
- `subscribers` — subscriber_id, full_name, email, signup_date, region, **device_platform**,
  **acquisition_channel**
- `subscriptions` — subscription_id, subscriber_id, plan, **billing_cycle**, start_date,
  end_date, status, **cancel_reason**, **mrr**
- `rentals` — rental_id, subscriber_id, title_id, rented_date, price, **payment_method**,
  **rating**

As predicted, **no new `core/distributions.py` helper was required** — everything composed
from existing `ctx.dist` / `ctx.rng.child` / catalog literals.

## Quick wins (realism enrichment)

- [x] **`plans.max_streams`** (`Int64`) — fixed lookup on plan name (Basic 1 / Standard 2 /
  Premium 4); add to the `PLANS` tuple in `constants.py` as the source of truth. Unlocks:
  concurrent-stream / household-value analysis per tier.
- [x] **`plans.video_quality`** (`Utf8`) — fixed lookup on plan (Basic SD / Standard HD /
  Premium UHD), same `PLANS` tuple. Unlocks: quality-tier slicing, price-per-quality.
- [x] **`plans.ad_supported`** (`Boolean`) — fixed lookup on plan (Basic true, others false).
  Unlocks: ad-tier vs ad-free revenue-mix slicing.
- [x] **`regions.currency`** (`Utf8`) — fixed lookup on region code (US USD / GB GBP / DE EUR /
  BR BRL / IN INR / JP JPY); add to the `REGIONS` tuple in `constants.py`. Unlocks: local-price
  presentation, currency-grouped reporting.
- [x] **`titles.runtime_minutes`** (`Int64`) — `ctx.dist.clamped_normal` keyed on `kind`
  (film ≈110±20, series episode ≈45±10), clamped to a sane floor. Unlocks: catalogue
  length/hours analysis, runtime-by-genre slicing.
- [x] **`titles.maturity_rating`** (`Utf8`) — `ctx.dist.choice` over a fixed
  `MATURITY_RATINGS` catalog (`{G, PG, PG-13, R, TV-MA}`) with a plausible weight vector.
  Unlocks: content-rating mix, kid-safe catalogue share by region (join through
  `title_availability`).
- [x] **`subscribers.device_platform`** (`Utf8`) — `ctx.dist.choice` over
  `{ios, android, web, smart_tv, roku}` weighted; a named child stream so existing subscriber
  draws don't shift. Unlocks: device-mix slicing, platform-share reporting.
- [x] **`rentals.payment_method`** (`Utf8`) — `ctx.dist.choice` over
  `{card, paypal, gift_card, wallet}` weighted, via a named child stream. Unlocks: tender-mix
  analysis on the PVOD revenue stream.

## High-leverage additions

> **Implemented (items 1–5).** All five landed with planted signals, scenario docs, and
> magnitude tests. Items 1 & 2 were co-designed: a single per-subscriber churn model in
> `tables/subscriptions.py` keys both cancel probability and tenure off acquisition channel
> **and** billing cadence. Scenario docs: `paid-channels-churn-faster.md`,
> `annual-plans-retain-better.md`, `cancellation-reasons-vary-by-segment.md`,
> `premium-rentals-rate-lower.md`, `premium-titles-score-higher.md`. Only item 6 (mrr) remains.
>
> **Deviations from the sketch** (the signal is per-row-keyed, so the flat `ctx.dist` helpers
> didn't fit): churn `status`/tenure are a per-row Bernoulli / per-row-λ Poisson scaled by
> channel+billing multipliers (not a flat `choice`); `cancel_reason` is a per-row reweighted
> inverse-CDF draw (weights vary by region/plan); `avg_rating` uses `child("avg_rating").
> numpy.normal(per_row_mean, sd)` + `np.clip` because the mean keys on `is_premium` per row
> (scalar `clamped_normal` can't); `rentals.rating` lands as a nullable `Int64` (from a
> `list[int | None]`), not `Int8`.

### 1. `subscribers.acquisition_channel`
- [x] Add `acquisition_channel` (`Utf8`, `{organic, paid_search, social, referral, partner}`,
  `ctx.dist.choice` weighted via a named child stream). The bare dimension is realism, but the
  *interesting* part is a subset signal.
- **Unlocks:** acquisition-mix / CAC-style segmentation; retention-by-channel.
- **Class:** **scenario-bearing** → route to `/scenario:draft-or-propose`. Signal: **paid
  channels (paid_search / social) churn faster / hold shorter tenure than organic + referral**
  — plant by keying the `subscriptions` tenure/status draw off the subscriber's channel
  (`subscriptions` already `depends_on ("subscribers", ...)`, so no new dependency). Today
  tenure is drawn independently of everything, so this is a genuine new signal, not a dup.

### 2. `subscriptions.billing_cycle`
- [x] Add `billing_cycle` (`Utf8`, `{monthly, annual}`, `ctx.dist.choice` weighted ~0.8/0.2
  via a named child stream). Composes with `plans.monthly_price` to derive booked revenue
  (annual = 12× at a discount).
- **Unlocks:** revenue-cadence / commitment analysis; MRR-vs-ARR framing.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Signal: **annual
  subscribers retain markedly better** (longer tenure, lower cancelled share) than monthly —
  plant by keying the tenure/status draw off `billing_cycle`. Distinct from item 1; both key
  the same tenure draw, so co-design them if built together.

### 3. `subscriptions.cancel_reason`
- [x] Add `cancel_reason` (`Utf8`, **nullable** — non-null only when `status = 'cancelled'`,
  null for active; `ctx.dist.choice` over `{price, content, technical, competitor, other}`
  via a named child stream, masked by status). No new dependency (status is in-table).
- **Unlocks:** churn-driver analysis; the "why do they leave" domain the collection lacks.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Signal: **reason
  concentrates by segment** — e.g. `content` dominates cancellations in narrow-catalogue
  regions (JP/IN, which license ~30–45% of titles), while `price` dominates on the Basic tier.
  Ties naturally to the existing `catalog-size-varies-by-region` scenario.

### 4. `rentals.rating`
- [x] Add `rating` (`Int8` 1–5, **nullable** — only a minority of rentals get rated; draw a
  `ctx.dist.bernoulli` "did they rate" mask, then `ctx.dist.integers`/`choice` for the score,
  both via named child streams). No new dependency.
- **Unlocks:** rental satisfaction / PVOD quality analysis without needing a watch-events
  table.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Signal: **the rare $19.99
  day-and-date tier rates lower than the $4.99/$6.99 catalogue tiers** (price-expectation
  gap / buyer's remorse) — plant by keying the score mean off `rentals.price`. Builds on the
  existing skewed rental-price ladder.

### 5. `titles.avg_rating`
- [x] Add `avg_rating` (`Float64` on a 1–10 scale, `ctx.dist.clamped_normal` clamped to
  `[1, 10]` via a named child stream). Populated for every title (a catalogue quality score).
- **Unlocks:** content-quality analysis; join to `title_availability`/`rentals` for
  quality-weighted catalogue and rental questions.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Signal candidate:
  **premium-eligible titles (`is_premium`) score higher than the back catalogue**, or a chosen
  show `genre` systematically under-performs — key the mean off `is_premium`/`genre`. If built
  as a flat, un-keyed score it is realism-only; the value is in the planted slice, so treat as
  scenario-bearing.

## Later / depends-on

### 6. `subscriptions.mrr` (derived convenience column)
- [x] **Built 2026-07-11.** Materialized `mrr` (`Float64`) = `plans.monthly_price` (monthly) or the
  annual-discounted monthly equivalent (`monthly_price × ANNUAL_MRR_FACTOR`, `ANNUAL_MRR_FACTOR =
  10/12`, "2 months free") when `billing_cycle = 'annual'`. Pure derivation, no RNG — existing
  columns stayed byte-identical. MRR-identity invariant added to `realism-guidance.md` with a
  single-assert test.

## Out of scope — new tables, not columns (→ `/data-collection:propose`)

- **Watch / viewing events.** Watch sessions, per-episode play events, and a
  show → season → episode hierarchy are a whole new fact table (+ FKs), already flagged as the
  intended expansion in `realism-guidance.md` ("No viewing/watch events"). `titles.avg_rating`
  (item 5) is the in-scope single-column stand-in for content quality.
- **Subscription lifecycle events.** Plan upgrades/downgrades and multiple subscriptions per
  account need an events table; `realism-guidance.md` records the flat one-per-account
  lifecycle as deliberate. `billing_cycle` (item 2) is the in-scope stand-in for commitment.
- **Devices table.** A per-account device registry (many devices per subscriber) is a new
  entity; `subscribers.device_platform` (quick win) is the in-scope single-column stand-in.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items.

- [ ] **No heavy-renter concentration.** Rentals spread ~uniformly across subscribers
      (rentals/subscriber ≈ Poisson, max a handful) — no whale minority driving PVOD revenue.
      The strongest realism-flavoured candidate (documented as a future scenario).
- [x] **Subscription lifecycle is birth-only.** ~~Rows capture the subscription window (signup)
      but not right-censoring / churn dynamics after it — a candidate future invariant.~~
      **Realized 2026-07-11:** cancellations are now right-censored at the window end — a churn
      dated on/after `end_date` reads `active` with a null `end_date` — so a cancelled `end_date`
      always settles strictly inside the window. Pure re-derivation off the existing
      is_cancelled / tenure draws (no new RNG), so `mrr` and every other column stayed
      byte-identical; observed cancelled share moved 0.214 → 0.185 at the fixture. See
      `realism-log.md`.
- [ ] **`is_premium` is release-date independent.** Newer releases aren't tilted toward the
      premium tier the way real PVOD is; the premium-by-release-year cross-tab reads flat
      (scenario-bearing).
- [ ] **Device/region mixes are flat, unplanted.** No device-mix-by-region or maturity-by-genre
      skew — realism dimensions to slice by, currently uniform.

## When the list is done

- [x] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
  rubric and invariant tests with the new columns (new dimensions to slice by, new invariants
  to pin — plan-attribute lookups, nullable `cancel_reason`/`rating` rules, rating bounds).
  Run `/data-collection:review-edit-regen-for-realism` for this collection.
