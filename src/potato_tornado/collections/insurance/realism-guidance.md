# Realism guidance — insurance

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** `policies.policyholder_id ∈ policyholders`,
  `policies.broker_id ∈ brokers`, `claims.policy_id ∈ policies`,
  `claims.adjuster_id ∈ adjusters`, `claim_payments.claim_id ∈ claims`,
  `claim_payments.adjuster_id ∈ adjusters` (and equals the settled claim's `adjuster_id` — a
  carried FK, not a fresh draw), `quotes.policyholder_id ∈ policyholders`, and every non-null
  `quotes.policy_id ∈ policies`.
- **Quote ↔ policy linkage.** A quote's `policy_id` is non-null **iff** `converted` is true;
  each policy has exactly **one** converting quote (`policy_id` is unique among converted
  quotes), and a converting quote's `quote_date ≤ policies.start_date`.
- **Payment exists iff settled.** A `claim_payments` row exists for a claim **iff** that
  claim's `status ∈ {approved, partial}`. Denied and open claims have no payment; there is at
  most one payment per claim (`claim_payments` is 1:1 with settled claims).
- **Payout bounds.** `0 ≤ paid_amount ≤ min(reported_amount, coverage_limit) − deductible`
  (the approved-equivalent, floored at 0). A `partial` pays 0.3–0.8× that, so a partial never
  pays more than an approved claim on the same facts would.
- **Temporal ordering.** `claim_date` falls within `[policies.start_date, policy term end]`
  and on/before `end_date`; `paid_date ≥ claim_date` (a 5–45 day settlement delay, stretched
  ×1.75 on litigated claims — see the litigation tax below).
- **Settlement-days identity.** `claim_payments.settlement_days = (paid_date − claim_date)` in
  whole days — a derived column, not an independent draw. The base is a 5–45 day integer;
  litigated claims stretch it ×1.75, so non-litigated values sit in `[5, 45]` and litigated
  ones extend up to `round(45 × 1.75) = 79` (the litigation cycle-time tax — see
  `scenarios/litigation-tax.md`).
- **Subrogation eligibility.** `claim_payments.subrogation_recovery_amount > 0` **only** on
  not-at-fault claims (the claim's `at_fault is False`) and always `≤ paid_amount` (it is a
  fraction of the payout). It is **null** on ineligible claims (at-fault, or non-auto where
  `at_fault` is null) and **0.0** on eligible-but-unrecovered claims.
- **Non-negativity / ordering.** `reported_amount > 0`, `annual_premium > 0`,
  `deductible ≥ 0`, `coverage_limit > deductible`, `term_months ∈ {6, 12}`.
- **Catalogs are fixed.** `policyholders.risk_tier ∈ {preferred, standard, high_risk}`;
  `policyholders.age_band ∈ {18-25, 26-40, 41-60, 60+}`; `policyholders.state` is a
  2-letter USPS code (50 states + DC); `policies.product ∈ {auto, home, renters}`;
  `policies.channel ∈ {broker, direct, aggregator}`;
  `policies.payment_frequency ∈ {monthly, quarterly, annual}`; `claims.peril ∈ PERILS`;
  `claims.status ∈ {open, approved, partial, denied}`;
  `claims.reported_channel ∈ {phone, app, broker, web}`;
  `policies.status ∈ {active, lapsed, cancelled}`;
  `adjusters.team ∈ {auto, property, liability, catastrophe}`;
  `adjusters.seniority ∈ {junior, senior, lead}`; `quotes.product ∈ {auto, home, renters}`;
  `claim_payments.settlement_method ∈ {check, ach, card}`;
  `adjuster_notes.water_cause ∈ {sudden, gradual}` on water-damage claims (null elsewhere).
- **Bounded enrichment ranges.** `policyholders.tenure_years ∈ [0, 15]`;
  `brokers.tenure_years ∈ [1, 30]`; `brokers.commission_rate ∈ [0.08, 0.15]`.
- **Bundled is derived.** `policies.bundled` is true **iff** the holder appears on ≥2
  `policies` rows — a computed flag, not a draw.
- **`at_fault` nullity.** `claims.at_fault` is non-null **iff** the claim's policy
  `product = 'auto'` (a liability posture only auto claims carry); it is null on every non-auto
  claim. `catastrophe_flag`, `fraud_flag`, and `litigated` are always non-null booleans.
- **Adjuster notes reconcile.** `adjuster_notes.claim_id ∈ claims` and is **1:1** with
  `claims` (exactly one note per claim). The dollar figure rendered in `body` equals the
  claim's `reported_amount` rounded to the nearest dollar (so a parsed estimate reconciles to
  within \$1 — no answer leaked). `adjuster_notes.water_cause ∈ {sudden, gradual}` **iff** the
  claim's `peril = water_damage`, and is **null** otherwise; it is a **withheld** answer key
  (the sudden/gradual coverage trigger is recorded only in the prose, never as a queryable
  `claims` column) whose value must match the cause a keyword parse of `body` recovers. See
  `scenarios/gradual-water-losses-settle-below-sudden.md`.
- **Claim status history.** `claim_status_history.claim_id ∈ claims`; each claim has exactly
  **3** transition rows walking `reported → under_review → its adjudication status`
  (`seq ∈ {1, 2, 3}`, `from_status` null only on `seq = 1`). `changed_at` starts at the claim's
  `claim_date` and **strictly increases** with `seq` within a claim (monotonic, no reopenings) —
  the reported→terminal gaps are stretched ×1.75 on litigated claims (both gaps by the same
  factor, so strict monotonicity is preserved; the litigation cycle-time tax). The terminal
  (`seq = 3`) `to_status` **equals** the claim's `status`, so the log reconciles with `claims`
  exactly.
- **Instalments reconcile.** `premium_billing.policy_id ∈ policies`; a policy has exactly
  `{monthly: 12, quarterly: 4, annual: 1}` instalments per its `payment_frequency`, and those
  instalments **sum to `annual_premium`** (to the cent). `amount > 0`;
  `due_date ≥ policies.start_date`; `paid_date` is null **iff** `status = missed`, and non-null
  `paid_date ≥ due_date`; `status ∈ {paid, late, missed}`.
- **Coverage lines reconcile.** `coverage_lines.policy_id ∈ policies`; a policy has exactly
  `len(COVERAGE_LINES[product])` lines (auto 3 / home 3 / renters 2), each `coverage_line` drawn
  from that product's catalog set. The per-line `line_premium_share` values **sum to
  `annual_premium`** (to the cent — the last line absorbs the rounding remainder) and are each
  `> 0`. `line_deductible = policies.deductible` on lines where the deductible applies and
  **`0.0` on liability lines** (a derived value, no draw); `line_limit > 0`. `line_limit` is a
  **descriptive** breakdown and is **deliberately not** reconciled against
  `policies.coverage_limit` — the payout path never reads it (see Deliberate simplifications).

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `brokers` = 40, `adjusters` = 40, `policyholders` = 4000,
  `policies` = 5000 (a holder may hold more than one), `premium_billing` ≈ 37,600 (one row per
  instalment: monthly×12 / quarterly×4 / annual×1 over the policies), `coverage_lines` ≈ 14,000
  (one row per coverage line: auto×3 / home×3 / renters×2 over the policies), `quotes` = 12,500
  (one converting quote per policy + non-converting; conversion ≈ 0.40), `claims` ≈ 620
  (frequency-derived, ~11% of policies), `claim_payments` ≈ 490 (~79% of claims — the settled
  share), `claim_status_history` = **3 × claims** ≈ 1,860 (one row per lifecycle stage),
  `adjuster_notes` = **1 × claims** ≈ 620 (one free-text loss-description note per claim).
- **Adjuster assignment.** Each claim's `adjuster_id` is drawn **uniformly** over the 40
  adjusters — no per-adjuster load or performance signal (mirrors `broker_id`). `team` ≈ auto
  0.40 / property 0.30 / liability 0.20 / catastrophe 0.10; `seniority` ≈ junior 0.50 / senior
  0.35 / lead 0.15 (both small-n, so noisy at `scale < 1`).
- **Quote conversion.** Overall ≈ **0.40** of quotes convert to a policy, drawn **independent**
  of premium and product (conversion is ~flat across premium quartiles). A converting quote is
  priced within ±5% of the bound `annual_premium`; non-converting quotes bootstrap their
  (product, premium) off a random policy, so the `quoted_premium` marginals match.
- **Risk-tier mix.** preferred 0.45 / standard 0.40 / high_risk 0.15.
- **Product mix.** auto 0.50 / home 0.30 / renters 0.20.
- **Holder demographics.** `age_band` ≈ 18-25 0.12 / 26-40 0.30 / 41-60 0.33 / 60+ 0.25;
  `tenure_years` **right-skewed** over [0, 15] (geometric decay, ratio 0.85 → mean ≈ 4.2,
  median 3; ~0.53 of holders ≤ 3 yr, ~0.065 ≥ 12 yr — a growing book, few long-tenured, no
  boundary pile); `state` population-weighted over the 50 states +
  DC (CA / TX / FL / NY the modes). All three are independent of `risk_tier` — slicing
  frequency/severity by them yields flat cuts (see Deliberate simplifications).
  `prior_claims_count` is a right-skewed `Poisson(0.6)` (mode 0, mean ≈ 0.6, most holders 0,
  max ~5) drawn with a **single tier-independent** λ — flat across risk tiers, so it carries
  no experience-rating signal (see Deliberate simplifications).
- **Policy attributes.** `channel` ≈ broker 0.50 / direct 0.30 / aggregator 0.20;
  `payment_frequency` ≈ monthly 0.55 / quarterly 0.15 / annual 0.30; `auto_renew` ≈ **0.70**
  true (Bernoulli); `bundled` ≈ **0.71** of policies true (scale-independent — it follows the
  fixed 5000/4000 policy-per-holder ratio: `1 − e^(−1.25) ≈ 0.71`). `renewal_count`
  right-skewed with **mode 0** (≈ **0.45** new business), `geometric(0.45) − 1` → mean ≈ 1.2,
  always ≥ 0 — an **abstract** lifecycle marker deliberately decoupled from `start_date` (see
  Deliberate simplifications). All independent of premium/tier.
- **Broker attributes.** `tenure_years` **right-skewed** over [1, 30] (geometric decay,
  ratio 0.90 → mean ≈ 8.5, newer producers outnumber veterans ≥20yr, monotonic taper to 30
  with no boundary pile); `commission_rate` uniform over [0.08, 0.15]. Both signal-free (no
  producer-performance coupling).
- **Claim FNOL channel.** `reported_channel` ≈ phone 0.40 / broker 0.25 / app 0.20 / web 0.15,
  independent of peril and severity.
- **Claim-context flags.** `at_fault` ≈ **0.55** true among the (non-null) auto claims;
  `catastrophe_flag` ≈ **0.10** overall, its *rate* conditioned on peril (weather ⇒ ≈ **0.35**,
  every other peril ≈ **0.03**) — only the rate varies, severity stays peril-independent;
  `fraud_flag` ≈ **0.04** (SIU referral); `litigated` ≈ **0.10** (attorney representation). Their
  *incidence* is a flat base rate drawn independently of tier, severity, adjuster, and
  adjudication outcome (measured fraud ≈ 0.046, litigated ≈ 0.109, cat|weather ≈ 0.36 vs
  cat|other ≈ 0.04 at full scale; small-n seed noise at `scale < 1`). **`litigated` is the one
  exception on *consequences*:** its incidence stays flat, but litigated claims carry a heavier
  `reported_amount`/`paid_amount` and a longer settlement/lifecycle cycle (the litigation tax —
  see `scenarios/litigation-tax.md`).
- **Billing outcome mix.** `premium_billing.status` ≈ paid 0.90 / late 0.07 / missed 0.03 —
  a low, flat delinquency rate drawn independently of policy, tier, and cadence (no
  concentration). On-time payments land within 3 days of `due_date`, late ones 7–40 days after.
- **annual_premium.** Lognormal (σ ≈ 0.4) whose median is the product base × tier multiplier,
  then nudged by the policy's coverage step and deductible (see next line) — median ≈
  **preferred \$850 / standard \$1,195 / high_risk \$2,070**. Right-skew within each tier.
  Premium multipliers 0.70 / 1.00 / 1.75.
- **Premium ↔ coverage / deductible (weak co-movement).** Premium rises with the coverage step
  (factor 0.90 / 1.00 / 1.15 for {0.5, 1.0, 2.0}×) and falls with the deductible (1.06 / 1.00 /
  0.92 for {\$250, \$500, \$1,000}), both centred on their weighted mean so the tier medians
  above are unchanged. Within a product+tier cell this shows as a **weak positive**
  premium↔coverage correlation (≈ **+0.15 to +0.24**) and a **weak negative** premium↔deductible
  correlation (≈ **−0.13**): mean premium climbs ~30% from the 0.5× to the 2.0× coverage step
  and drops ~13% from the \$250 to the \$1,000 deductible. It is deliberately buried in the
  lognormal scatter — a plausible underwriting nudge, **not** a discoverable subset gap.
- **coverage_limit / deductible.** Coverage is the product base (auto \$60k / home \$300k /
  renters \$30k) × a per-policy step {0.5, 1.0, 2.0}; deductible ∈ {\$250, \$500, \$1,000}
  weighted 0.30 / 0.45 / 0.25, always `< coverage_limit`.
- **Coverage-line split (`coverage_lines`).** Each policy fans out into its product's lines
  (auto: liability / collision / comprehensive; home: dwelling / contents / liability; renters:
  contents / liability). `line_premium_share` splits `annual_premium` around the catalog base
  weights (auto 0.45 / 0.35 / 0.20; home 0.55 / 0.25 / 0.20; renters 0.65 / 0.35) with a
  per-line lognormal jitter (σ ≈ 0.25) then normalized — so the mean shares land near the
  catalog weights but no policy is a constant ratio (measured means track the catalog to
  ±0.01). `line_limit` is the catalog base line limit (liability \$100k / collision \$40k /
  comprehensive \$25k / dwelling \$300k / contents \$120k or \$30k) × a lognormal jitter (σ ≈
  0.15) rounded to the nearest \$100 — **near-continuous** at the line grain (~1,400 distinct
  values vs the 7-value policy `coverage_limit` lattice). All signal-free — the split is a
  descriptive premium breakdown, coupled to nothing.
- **Claim frequency (the "frequency" half).** Per-policy `Poisson(λ × exposed_years)`, λ by
  tier = 0.09 / 0.18 / 0.42, where `exposed_years` is the policy term clipped to `end_date`.
  Overall ≈ **11%** of policies file ≥1 claim; high-risk policies claim ~4.4× as often as
  preferred. See `scenarios/frequency-severity.md`.
- **Claim timing.** Because counts scale with each policy's *in-window* exposed span (not the
  full contractual term), the observed annual claim rate equals λ and claim volume tracks the
  in-force with **no pile-up at `end_date`** — claims-per-in-force is flat across the window
  (the final 90 days hold no more claims than the preceding 90). The book fills from zero at
  `start_date`, so total claim volume still *ramps* over the three years (≈ 132 → 237 per
  calendar year at `scale=1.0`, ~1.8×) purely from a growing in-force, not from rising per-policy
  frequency — see the cold-start note under Deliberate simplifications.
- **reported_amount (the "severity" half).** Lognormal median ≈ **\$6.4k** (≈ **\$6.5–7.0k**
  with the litigation loading below), σ ≈ 1.0 → p95 ≈ \$30–34k, max past \$50k. Independent of
  tier, product, and peril (a deliberate simplification); the **one coupling** is a **×2.2**
  loading on the ~11% of litigated claims (the litigation tax — see
  `scenarios/litigation-tax.md`), which nudges the overall median/mean up a few points.
- **Adjudication mix.** approved 0.62 / partial 0.16 / denied 0.14 / open 0.08 (measured ≈
  0.61 / 0.18 / 0.13 / 0.08) for every peril **except** `water_damage`, whose adjudication
  now **conditions on the note-native sudden/gradual cause**: `sudden` water claims keep the
  book mix, `gradual` ones draw a harder mix (approved 0.22 / partial 0.25 / denied 0.45 /
  open 0.08). So a cut of water-damage adjudication by cause is **not** flat — see
  `scenarios/gradual-water-losses-settle-below-sudden.md`. See also
  `scenarios/adjudication-funnel-reported-vs-paid.md`.
- **paid_amount.** approved = `clip(min(reported, coverage_limit) − deductible, 0, ∞)`;
  partial = 0.3–0.8× that. Total paid ≈ **58–62%** of total reported — a couple points below
  a book without the water-cause tilt, because the ~40% of water claims labelled `gradual`
  deny/partial far more (their slice pays ≈ 0.33 vs. ≈ 0.63 for sudden), pulling the blended
  `water_damage` realization to ≈ 0.52. (The litigation loading pushes the other way, raising
  `reported` faster than `paid` on the litigated claims it caps.)
- **Settlement detail.** `settlement_days` a 5–45 day uniform integer draw (non-litigated
  mean ≈ 25 days), **stretched ×1.75 on litigated claims** (litigated mean ≈ 42 days, extending
  up to `round(45 × 1.75) = 79` — the litigation cycle-time tax, see
  `scenarios/litigation-tax.md`); `settlement_method` ≈ **ach 0.45 / check 0.35 / card 0.20**
  (measured ≈ 0.46 / 0.35 / 0.20). `settlement_method` is flat (no per-adjuster/amount/tier
  coupling); `settlement_days` is flat **except** for the litigation stretch (a
  settlement-time-varies-by-adjuster cut is a candidate scenario, not planted here).
- **Subrogation.** ≈ **25%** of eligible (not-at-fault auto) claims recover, ≈ **5–6%** of all
  settled claims carry a positive `subrogation_recovery_amount` (measured ≈ 0.055 at full
  scale); the recovered amount is **0.20–0.60× `paid_amount`**. A net-of-subro loss ratio
  (gross paid vs. paid − recovery) is the intended use; the recovery is flat (no tier/severity
  coupling beyond the at-fault gate).
- **Loss ratio (Σ paid ÷ Σ premium).** Overall ≈ **0.63** (≈0.62–0.69 across seeds — the
  water-cause adjudication tilt shaves ≈2 points off a book without it, but stays in band),
  rising **preferred ≈ 0.46 → standard ≈ 0.65 → high_risk ≈ 0.90** (tier means over several seeds; the
  per-tier ratios carry ±0.15 seed noise and the standard/high_risk gap can narrow or invert on
  a given seed — see `scenarios/loss-ratio-rises-with-risk-tier.md`). These sit a few points
  above a litigation-free book: the litigation tax adds ~11% of claims paying ≈1.8× and lifts
  every tier roughly uniformly (litigation incidence is tier-independent), so the *ordering* is
  untouched.
- **peril mix.** Skewed (not uniform): collision ≈ 0.28 / water_damage ≈ 0.22 / weather ≈ 0.20
  / theft ≈ 0.14 / liability ≈ 0.10 / fire ≈ 0.06 — the common personal-lines perils dominate,
  fire is rare. This is a **marginal** frequency only; peril *frequency* stays independent of
  product and geography (see Deliberate simplifications). Measured shares carry small-n seed
  noise. **Within `water_damage`**, a note-native cause splits the claims ≈ **57% sudden /
  43% gradual** (`GRADUAL_SHARE = 0.40`) and drives the adjudication gap above — the label
  lives only in `adjuster_notes.body` (see `scenarios/gradual-water-losses-settle-below-sudden.md`).

## Deliberate simplifications (intended — do not "fix")

- **One payout per claim, monotonic to a single terminal status** — no reserves or installment
  settlements, and **no reopenings**. `claim_status_history` now makes the lifecycle explicit,
  logging the ordered walk `reported → under_review → the claim's terminal status` with
  advancing timestamps — but the walk is still **monotonic to one terminal state**: a claim
  never reopens or revisits a status, its `claim_status_history` terminal row reconciles with
  `claims.status`, and there is still exactly one `claim_payments` row per settled claim. (The
  earlier "adjudicated once, no transition log" simplification is thus partly relaxed — the
  transitions are modelled — while the single-terminal-state / no-reopening guarantee stands.)
- **Premium is a flat annual figure** — no mid-term endorsements, no proration on
  cancel/lapse. `policies.status` (active/lapsed/cancelled) carries no premium or date
  adjustment; a lapsed policy still shows its full `annual_premium`. `premium_billing`
  **decomposes** that annual figure into instalments (which sum back to it) but does not change
  it — the schedule is a billing calendar, not a re-rating.
- **Billing delinquency carries no signal** — `premium_billing.status` is drawn independently
  of the policy, its tier, and its `payment_frequency`, so the missed/late rate is flat across
  every slice. A delinquency that concentrates (e.g. monthly-pay or high_risk policies miss
  more) is a candidate scenario, not planted here.
- **"Loss ratio" is pure paid ÷ premium** — no reinsurance, expenses, commissions, or
  investment income. It is a teaching ratio, not a GAAP combined ratio.
- **Severity and peril are independent** of policyholder geography, vehicle/home specifics,
  product, and risk tier — only *frequency* varies by tier, not *severity*. A real book would
  couple severity to product and peril; here the two halves are cleanly separable by design. The
  **one** deliberate severity coupling is the litigation tax (a ×2.2 `reported_amount` loading on
  litigated claims — see the claim-context-flags bullet below); severity stays independent of
  every other covariate.
- **Most claim-context flags carry no signal** — `at_fault` and `fraud_flag` are flat base
  rates drawn independently of severity, tier, adjudication outcome, and adjuster;
  `catastrophe_flag` conditions its *rate* on the weather peril but leaves `reported_amount`
  peril-independent (consistent with the severity-independence bullet above). So the
  cat-vs-attritional **severity** split and fraud-denies-more (an inflated `denied` share and
  lower settlements) remain candidate scenarios, not planted here. **`litigated` is the
  exception**: its incidence stays a flat base rate, but its consequences *are* coupled — the
  **litigation tax** (heavier `reported_amount`/`paid_amount` + a longer settlement/lifecycle
  cycle) is planted, so a cut by litigation status is **not** flat. See
  `scenarios/litigation-tax.md`.
- **`policies.coverage_limit` takes a small set of values** (product base × one of three
  steps), not a continuous underwritten limit; `deductible` is a 3-value ladder. This
  **policy-level lattice stays** — it is what the claim → payout path reads, so keeping it a
  legible 7-value set keeps the payout arithmetic legible. `coverage_lines.line_limit` **does**
  relax the lattice, but only at the line grain (near-continuous, ~1,400 distinct values), and
  descriptively — it is never read by a payout (see next bullet).
- **The payout path stays policy-level; `coverage_lines` is additive/descriptive.** The
  per-line breakdown is a **premium-side** refinement only: it splits `annual_premium` across a
  policy's coverage lines and gives each a jittered `line_limit` / derived `line_deductible`,
  but **no claim maps to a line**. Claims still price against the policy-level `coverage_limit`
  and `deductible`, and `line_limit` is **deliberately not reconciled** against
  `coverage_limit` (their sum need not equal it). Line-level loss ratios — mapping a claim's
  peril to the covered line and pricing the payout against `line_limit` — are a candidate
  scenario (a deeper payout-model rework), not planted here.
- **`broker_id` and `region` carry no signal** — brokers don't influence premium, claim
  frequency, or loss ratio; the broker dim exists for join practice, not a producer-performance
  scenario (a natural future addition). `broker.commission_rate` and `broker.tenure_years` are
  likewise inert producer attributes.
- **Enrichment covariates carry no signal** — `policyholders.age_band` / `tenure_years` /
  `state` / `prior_claims_count`, `policies.channel` / `payment_frequency` / `auto_renew` /
  `renewal_count`, and `claims.reported_channel` are all drawn independently of frequency,
  severity, premium, and the adjudication outcome. They exist for slicing and joins, so any cut
  by them is flat; a demographic or channel-driven signal is a candidate scenario, not planted
  here. In particular `prior_claims_count` uses one tier-independent λ, so **experience rating**
  (in-window frequency rising with prior history) is deliberately absent — a candidate scenario,
  not planted. (`bundled` is derived from the multi-policy structure, so it is real but
  signal-free.)
- **`adjuster_id` carries no signal** — assignment is uniform, so settlement time, partial rate,
  and caseload are flat across adjusters and teams. `claim_payments.adjuster_id` carries the
  handling adjuster onto the payment (enabling a per-adjuster cycle-time roll-up), and
  `settlement_days` / `settlement_method` are drawn independently of it, so that roll-up is
  deliberately flat. The dim is for join/rollup practice; a handler-level performance outlier
  (settlement time or partial rate varying by adjuster) is a candidate scenario, not planted
  here.
- **Quote conversion carries no signal** — `converted` is drawn independent of `quoted_premium`
  and `product`, so the conversion rate is ~flat (no price-elasticity funnel). The `quotes`
  table gives an upstream sales stage to join through; a premium/product-driven conversion
  signal is a candidate scenario, not planted here.
- **Cold-start book** — the in-force grows from zero at the window's `start_date` (no
  backdated policies), so total claim volume ramps up ≈ 1.8× across the three years purely
  because more policies are in force, not because per-policy frequency changes. Per-policy
  frequency is flat over time (claims-per-in-force is constant); a YoY "claims are rising"
  read is an exposure-growth artifact, not a deteriorating book. Consequently
  `policies.renewal_count` is an **abstract** book-mix marker (new-vs-renewal split), drawn
  **decoupled from `start_date`**: a non-zero count would imply pre-window terms that the
  cold-start book doesn't model, so it must not be read as a real prior-term history or
  correlated with policy age. It exists for the new-vs-renewal cut, not a retention timeline.

## How to review

```sql
-- payment exists iff settled (expect 0 violations)
select count(*) filter (where c.status in ('approved','partial') and pay.claim_id is null)
     + count(*) filter (where c.status in ('denied','open') and pay.claim_id is not null) as bad
from claims c left join claim_payments pay using (claim_id);

-- payout never exceeds the approved-equivalent cap (expect 0)
select count(*) as over_cap
from claim_payments pay
join claims c using (claim_id)
join policies p using (policy_id)
where pay.paid_amount > greatest(least(c.reported_amount, p.coverage_limit) - p.deductible, 0) + 0.01;

-- ~11% of policies claim; severity is heavy-tailed
select count(distinct policy_id)::float / (select count(*) from policies) as claim_rate,  -- ≈ 0.11
       quantile_cont(reported_amount, 0.95) as sev_p95                                    -- ≈ 31000
from claims;

-- no claim pile-up at the window end: the last 90 days hold ≲ the prior 90 (expect ratio ≈ 1)
select count(*) filter (where claim_date >= (select max(claim_date) from claims) - interval 90 day)::float
     / nullif(count(*) filter (where claim_date >= (select max(claim_date) from claims) - interval 180 day
                                 and claim_date <  (select max(claim_date) from claims) - interval 90 day), 0) as tail_ratio
from claims;

-- loss ratio rises with tier (≈0.46 → ≈0.90; ±0.15 seed noise, gap can narrow)
select ph.risk_tier,
       sum(pay.paid_amount) / (select sum(p2.annual_premium) from policies p2
                               join policyholders ph2 using (policyholder_id)
                               where ph2.risk_tier = ph.risk_tier) as loss_ratio
from claim_payments pay
join claims c using (claim_id)
join policies p using (policy_id)
join policyholders ph using (policyholder_id)
group by ph.risk_tier order by loss_ratio;

-- quote funnel: ~40% convert, and the linkage is consistent (expect conv_rate ≈ 0.40, bad = 0)
select avg(converted::int)                                            as conv_rate,  -- ≈ 0.40
       count(*) filter (where converted <> (policy_id is not null))   as bad          -- expect 0
from quotes;

-- adjuster assignment is flat: settlement time shouldn't vary by adjuster (spread ≈ 0)
select stddev(mean_days) as across_adjuster_spread  -- small; no handler signal
from (
  select c.adjuster_id, avg(pay.paid_date - c.claim_date) as mean_days
  from claims c join claim_payments pay using (claim_id)
  group by c.adjuster_id
) t;

-- status history reconciles: every claim's terminal transition matches its status (bad = 0)
select count(*) as bad
from claim_status_history h
join claims c using (claim_id)
where h.seq = 3 and h.to_status <> c.status;

-- subrogation recovers only from not-at-fault claims and never exceeds the payout (bad = 0)
select count(*) as bad
from claim_payments pay
join claims c using (claim_id)
where pay.subrogation_recovery_amount > 0
  and (c.at_fault is distinct from false or pay.subrogation_recovery_amount > pay.paid_amount);

-- adjuster notes are 1:1 with claims and water_cause is set iff water_damage (bad = 0)
select count(*) filter (where n.claim_id is null)                                       -- unmatched
     + (select count(*) - count(distinct claim_id) from adjuster_notes)                 -- duplicate notes
     + count(*) filter (where (c.peril = 'water_damage') <> (n.water_cause is not null)) as bad
from claims c left join adjuster_notes n using (claim_id);

-- water-damage adjudication is NOT flat by the note-native cause: gradual settles ~2x
-- below sudden (parse the note; expect gradual ≈ 0.33 vs sudden ≈ 0.63 at full scale)
with parsed as (
  select n.claim_id,
         case when n.body ~* '(seepage|gradual|long-term|wear|deterioration|over time|maintenance)' then 'gradual'
              when n.body ~* '(burst|sudden|accidental discharge|ruptured|sprang a leak)' then 'sudden' end as cause
  from adjuster_notes n join claims c using (claim_id) where c.peril = 'water_damage')
select p.cause, round(sum(coalesce(pay.paid_amount, 0)) / sum(c.reported_amount), 3) as paid_over_reported
from parsed p join claims c using (claim_id) left join claim_payments pay using (claim_id)
group by p.cause;
```
