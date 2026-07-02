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
- **Subscription status.** active 0.78 / cancelled 0.22.
- **Tenure.** Whole months ~ Poisson(6)+1, capped at 24 (right-skewed).
- **Content mix.** series 0.60 / film 0.40; ~25% of titles are premium-rental eligible.
- **Region subscriber mix.** US 0.34 / BR 0.16 / IN 0.16 / GB 0.14 / DE 0.12 / JP 0.08.
- **Catalogue density by region.** Per-title licensing probability: US 0.85 / GB 0.60 /
  DE 0.55 / BR 0.50 / IN 0.45 / JP 0.30 — so catalogue size runs US (~85%+ of titles) down
  to JP (~30%). See `scenarios/catalog-size-varies-by-region.md`.

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
- **No viewing/watch events.** Watch sessions, ratings, and a show → season → episode
  hierarchy are the intended expansion; only the subscription and rental revenue streams
  exist today.
- **Flat lifecycle.** One subscription per account, no plan upgrades/downgrades, and tenure
  is drawn independently of plan and region — a natural future churn scenario.
- **Rentals are independent of tenure.** A subscriber can rent on any date in the window,
  regardless of whether their subscription was active then. Tightening rentals to fall
  within an active subscription window is a candidate future invariant.
