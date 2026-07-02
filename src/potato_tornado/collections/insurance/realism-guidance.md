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
  `quotes.policyholder_id ∈ policyholders`, and every non-null `quotes.policy_id ∈ policies`.
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
  and on/before `end_date`; `paid_date ≥ claim_date` (a 5–45 day settlement delay).
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
  `adjusters.seniority ∈ {junior, senior, lead}`; `quotes.product ∈ {auto, home, renters}`.
- **Bounded enrichment ranges.** `policyholders.tenure_years ∈ [0, 15]`;
  `brokers.tenure_years ∈ [1, 30]`; `brokers.commission_rate ∈ [0.08, 0.15]`.
- **Bundled is derived.** `policies.bundled` is true **iff** the holder appears on ≥2
  `policies` rows — a computed flag, not a draw.
- **Instalments reconcile.** `premium_billing.policy_id ∈ policies`; a policy has exactly
  `{monthly: 12, quarterly: 4, annual: 1}` instalments per its `payment_frequency`, and those
  instalments **sum to `annual_premium`** (to the cent). `amount > 0`;
  `due_date ≥ policies.start_date`; `paid_date` is null **iff** `status = missed`, and non-null
  `paid_date ≥ due_date`; `status ∈ {paid, late, missed}`.

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `brokers` = 40, `adjusters` = 40, `policyholders` = 4000,
  `policies` = 5000 (a holder may hold more than one), `premium_billing` ≈ 37,600 (one row per
  instalment: monthly×12 / quarterly×4 / annual×1 over the policies), `quotes` = 12,500 (one
  converting quote per policy + non-converting; conversion ≈ 0.40), `claims` ≈ 620
  (frequency-derived, ~11% of policies), `claim_payments` ≈ 490 (~79% of claims — the settled
  share).
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
- **Policy attributes.** `channel` ≈ broker 0.50 / direct 0.30 / aggregator 0.20;
  `payment_frequency` ≈ monthly 0.55 / quarterly 0.15 / annual 0.30; `auto_renew` ≈ **0.70**
  true (Bernoulli); `bundled` ≈ **0.71** of policies true (scale-independent — it follows the
  fixed 5000/4000 policy-per-holder ratio: `1 − e^(−1.25) ≈ 0.71`). All independent of
  premium/tier.
- **Broker attributes.** `tenure_years` uniform integer over [1, 30]; `commission_rate`
  uniform over [0.08, 0.15]. Both signal-free (no producer-performance coupling).
- **Claim FNOL channel.** `reported_channel` ≈ phone 0.40 / broker 0.25 / app 0.20 / web 0.15,
  independent of peril and severity.
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
- **Claim frequency (the "frequency" half).** Per-policy `Poisson(λ × exposed_years)`, λ by
  tier = 0.09 / 0.18 / 0.42, where `exposed_years` is the policy term clipped to `end_date`.
  Overall ≈ **11%** of policies file ≥1 claim; high-risk policies claim ~4.4× as often as
  preferred. See `scenarios/frequency-severity.md`.
- **Claim timing.** Because counts scale with each policy's *in-window* exposed span (not the
  full contractual term), the observed annual claim rate equals λ and claim volume tracks the
  in-force with **no pile-up at `end_date`** — claims-per-in-force is flat across the window
  (the final 90 days hold no more claims than the preceding 90). The book fills from zero at
  `start_date`, so total claim volume still *ramps* over the three years (≈ 130 → 310 per
  calendar year at `scale=1.0`) purely from a growing in-force, not from rising per-policy
  frequency — see the cold-start note under Deliberate simplifications.
- **reported_amount (the "severity" half).** Lognormal median ≈ **\$6.4k**, σ ≈ 1.0 → p95 ≈
  \$30k, max past \$50k. Independent of tier, product, and peril (a deliberate simplification).
- **Adjudication mix.** approved 0.62 / partial 0.16 / denied 0.14 / open 0.08 (measured ≈
  0.61 / 0.18 / 0.13 / 0.08). See `scenarios/adjudication-funnel-reported-vs-paid.md`.
- **paid_amount.** approved = `clip(min(reported, coverage_limit) − deductible, 0, ∞)`;
  partial = 0.3–0.8× that. Total paid ≈ 65% of total reported.
- **Loss ratio (Σ paid ÷ Σ premium).** Overall ≈ **0.61**, rising **preferred ≈ 0.43 →
  standard ≈ 0.60 → high_risk ≈ 0.85** (tier means over several seeds; the per-tier ratios
  carry ±0.15 seed noise and the standard/high_risk gap can narrow or invert on a given seed —
  see `scenarios/loss-ratio-rises-with-risk-tier.md`).
- **peril mix.** Skewed (not uniform): collision ≈ 0.28 / water_damage ≈ 0.22 / weather ≈ 0.20
  / theft ≈ 0.14 / liability ≈ 0.10 / fire ≈ 0.06 — the common personal-lines perils dominate,
  fire is rare. This is a **marginal** frequency only; peril stays independent of product and
  geography (see Deliberate simplifications). Measured shares carry small-n seed noise.

## Deliberate simplifications (intended — do not "fix")

- **One payout per claim** — no reserves, reopenings, or installment settlements. A claim is
  adjudicated once to a single terminal status.
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
  couple severity to product and peril; here the two halves are cleanly separable by design.
- **`coverage_limit` takes a small set of values** (product base × one of three steps), not a
  continuous underwritten limit; `deductible` is a 3-value ladder. This keeps the payout
  arithmetic legible.
- **`broker_id` and `region` carry no signal** — brokers don't influence premium, claim
  frequency, or loss ratio; the broker dim exists for join practice, not a producer-performance
  scenario (a natural future addition). `broker.commission_rate` and `broker.tenure_years` are
  likewise inert producer attributes.
- **Enrichment covariates carry no signal** — `policyholders.age_band` / `tenure_years` /
  `state`, `policies.channel` / `payment_frequency` / `auto_renew`, and
  `claims.reported_channel` are all drawn independently of frequency, severity, premium, and
  the adjudication outcome. They exist for slicing and joins, so any cut by them is flat; a
  demographic or channel-driven signal is a candidate scenario, not planted here. (`bundled` is
  derived from the multi-policy structure, so it is real but signal-free.)
- **`adjuster_id` carries no signal** — assignment is uniform, so settlement time, partial rate,
  and caseload are flat across adjusters and teams. The dim is for join/rollup practice; a
  handler-level performance outlier is a candidate scenario, not planted here.
- **Quote conversion carries no signal** — `converted` is drawn independent of `quoted_premium`
  and `product`, so the conversion rate is ~flat (no price-elasticity funnel). The `quotes`
  table gives an upstream sales stage to join through; a premium/product-driven conversion
  signal is a candidate scenario, not planted here.
- **Cold-start book** — the in-force grows from zero at the window's `start_date` (no
  backdated policies), so total claim volume ramps up ≈ 2.3× across the three years purely
  because more policies are in force, not because per-policy frequency changes. Per-policy
  frequency is flat over time (claims-per-in-force is constant); a YoY "claims are rising"
  read is an exposure-growth artifact, not a deteriorating book.

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
       quantile_cont(reported_amount, 0.95) as sev_p95                                    -- ≈ 30000
from claims;

-- no claim pile-up at the window end: the last 90 days hold ≲ the prior 90 (expect ratio ≈ 1)
select count(*) filter (where claim_date >= (select max(claim_date) from claims) - interval 90 day)::float
     / nullif(count(*) filter (where claim_date >= (select max(claim_date) from claims) - interval 180 day
                                 and claim_date <  (select max(claim_date) from claims) - interval 90 day), 0) as tail_ratio
from claims;

-- loss ratio rises with tier (≈0.43 → ≈0.85; ±0.15 seed noise, gap can narrow)
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
```
