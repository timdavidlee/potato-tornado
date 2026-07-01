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
  `subscriptions.plan ∈ plans.plan`, `rentals.subscriber_id ∈ subscribers`, and
  `rentals.title_id ∈ titles`.
- **One subscription per subscriber.** Exactly one `subscriptions` row per subscriber, its
  `start_date` equal to the subscriber's `signup_date`.
- **Lifecycle dates.** `status = 'cancelled'` rows have a non-null `end_date` strictly after
  `start_date`; `status = 'active'` rows have a null `end_date`.
- **Rentals hit premium titles.** Every `rentals.title_id` references a title with
  `is_premium = true` (unless a tiny scale produced no premium titles, in which case rentals
  fall back to the full catalogue).
- **Rental price is a known price point.** `rentals.price ∈ {4.99, 6.99, 19.99}`.
- **Placeholder title names are unique.** `titles.name` values do not repeat.

## Distributions & mixes (should look like the real world)

- **Plan mix.** Basic 0.30 / Standard 0.50 (largest) / Premium 0.20. See
  `scenarios/standard-is-the-most-popular-plan.md`.
- **Subscription status.** active 0.78 / cancelled 0.22.
- **Tenure.** Whole months ~ Poisson(6)+1, capped at 24 (right-skewed).
- **Content mix.** series 0.60 / film 0.40; ~25% of titles are premium-rental eligible.

## Deliberate simplifications (intentional — do not "fix")

- **Placeholder title names.** `titles.name` is generated from stand-in word lists and will
  be replaced by a curated fake-show catalogue. Do not treat the current names as final.
- **No viewing/watch events.** Watch sessions, ratings, and a show → season → episode
  hierarchy are the intended expansion; only the subscription and rental revenue streams
  exist today.
- **Flat lifecycle.** One subscription per account, no plan upgrades/downgrades, and tenure
  is drawn independently of plan — a natural future churn scenario.
- **Rentals are independent of tenure.** A subscriber can rent on any date in the window,
  regardless of whether their subscription was active then. Tightening rentals to fall
  within an active subscription window is a candidate future invariant.
