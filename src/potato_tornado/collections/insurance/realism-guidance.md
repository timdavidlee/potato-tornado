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
  `claim_payments.claim_id ∈ claims`.
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
  `policies.product ∈ {auto, home, renters}`; `claims.peril ∈ PERILS`;
  `claims.status ∈ {open, approved, partial, denied}`;
  `policies.status ∈ {active, lapsed, cancelled}`.

## Distributions & mixes (should look like the real world)

- **Row counts (`scale=1.0`).** `brokers` = 40, `policyholders` = 4000, `policies` = 5000
  (a holder may hold more than one), `claims` ≈ 620 (frequency-derived, ~11% of policies),
  `claim_payments` ≈ 490 (~79% of claims — the settled share).
- **Risk-tier mix.** preferred 0.45 / standard 0.40 / high_risk 0.15.
- **Product mix.** auto 0.50 / home 0.30 / renters 0.20.
- **annual_premium.** Lognormal (σ ≈ 0.4) whose median is the product base × tier
  multiplier — median ≈ **preferred \$860 / standard \$1,210 / high_risk \$2,120**. Right-skew
  within each tier. Premium multipliers 0.70 / 1.00 / 1.75.
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
- **Loss ratio (Σ paid ÷ Σ premium).** Overall ≈ **0.62**, rising **preferred ≈ 0.43 →
  standard ≈ 0.67 → high_risk ≈ 0.79** (tier means; the standard/high_risk gap is narrow and
  can invert on a given seed — see `scenarios/loss-ratio-rises-with-risk-tier.md`).
- **peril mix.** Roughly uniform over the six perils — no product or geography coupling.

## Deliberate simplifications (intended — do not "fix")

- **One payout per claim** — no reserves, reopenings, or installment settlements. A claim is
  adjudicated once to a single terminal status.
- **Premium is a flat annual figure** — no mid-term endorsements, no proration on
  cancel/lapse. `policies.status` (active/lapsed/cancelled) carries no premium or date
  adjustment; a lapsed policy still shows its full `annual_premium`.
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
  scenario (a natural future addition).
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

-- loss ratio rises with tier (≈0.43 → ≈0.79; standard↔high_risk gap is narrow)
select ph.risk_tier,
       sum(pay.paid_amount) / (select sum(p2.annual_premium) from policies p2
                               join policyholders ph2 using (policyholder_id)
                               where ph2.risk_tier = ph.risk_tier) as loss_ratio
from claim_payments pay
join claims c using (claim_id)
join policies p using (policy_id)
join policyholders ph using (policyholder_id)
group by ph.risk_tier order by loss_ratio;
```
