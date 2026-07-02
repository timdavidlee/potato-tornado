# insurance — collection proposal

- **Domain:** a property-and-casualty insurer: policyholders buy policies that earn
  premium, a minority file claims, each claim is adjudicated to a payout (or
  denied), and the book is measured by its loss ratio.
- **Teaching value:** the first collection built on a **frequency-severity** model —
  *whether* a policy claims (a rare Bernoulli/Poisson event) is separate from *how
  much* a claim costs (a heavy right-skew severity). Most policies never claim; the
  few that do have a fat-tailed payout. On top of that sits a **loss ratio**
  (Σ paid ÷ Σ premium) that rises with risk tier — a portfolio-level plan-vs-actual
  (premium collected vs claims paid) none of the existing four teach, plus an
  adjudication funnel (reported → approved/partial/denied → paid).

## Tables

Build order (a DAG): `agents`, `policyholders` → `policies` → `claims` →
`claim_payments`.

- `agents` — the selling-agent dim. Columns: `agent_id: Utf8` (`AGT-001`),
  `full_name: Utf8` + `email: Utf8` (from `ctx.entities.people`),
  `region: Utf8`. `depends_on=()`.

- `policyholders` — the insured-party dim. Columns:
  `policyholder_id: Utf8` (`PH-000001`),
  `full_name: Utf8` + `email: Utf8` (from `ctx.entities.people`),
  `city: Utf8` (from `ctx.entities.cities`),
  `risk_tier: Utf8` (`preferred`/`standard`/`high_risk`, weighted).
  `depends_on=()`.

- `policies` — one row per policy sold. Columns: `policy_id: Utf8` (`POL-0000001`),
  `policyholder_id: Utf8 → policyholders.policyholder_id`,
  `agent_id: Utf8 → agents.agent_id`,
  `product: Utf8` (`auto`/`home`/`renters`, from `constants.PRODUCTS`),
  `start_date: Date` (spread across the window), `term_months: Int64` (6 or 12),
  `annual_premium: Float64` (tier-driven, right-skew),
  `coverage_limit: Float64`, `deductible: Float64`,
  `status: Utf8` (`active`/`lapsed`/`cancelled`).
  `depends_on=("policyholders", "agents")`.

- `claims` — the filings; **most policies produce zero, a few produce one or more**.
  Columns: `claim_id: Utf8` (`CLM-0000001`),
  `policy_id: Utf8 → policies.policy_id`,
  `claim_date: Date` (within the policy term and the window),
  `peril: Utf8` (from `constants.PERILS`),
  `reported_amount: Float64` (right-skew severity),
  `status: Utf8` (`open`/`approved`/`partial`/`denied`).
  `depends_on=("policies",)`.

- `claim_payments` — the payout (the **actual**), one row per **settled**
  (`approved`/`partial`) claim; denied and open claims get no row. Columns:
  `payment_id: Utf8` (`PAY-0000001`),
  `claim_id: Utf8 → claims.claim_id`,
  `paid_amount: Float64`, `paid_date: Date` (≥ the claim date).
  `depends_on=("claims", "policies")` — reads `coverage_limit`/`deductible` from
  `policies` to bound the payout.

Only settled claims have a `claim_payments` row, so a student must **left-join**
claims to payments and treat the missing side as \$0 — the teaching hook for the
denial funnel.

## Constants

`constants.py` candidates (each used by two or more tables):

- `RISK_TIERS` — `(tier, premium_multiplier, annual_claim_lambda)`, read by
  `policies` (premium) and `claims` (per-policy claim frequency).
- `PRODUCTS` — `(product, premium_median, coverage_limit, weight)`, read by
  `policies` (premium/limit) and referenced by scenarios.
- `PERILS` — the peril catalog (`collision`/`theft`/`weather`/`liability`/…),
  read by `claims` and the realism doc.

Single-table literals (deductible ladder, region list) stay inline.

## Distributions & target magnitudes

All numbers are **targets to plant**, to be firmed up after the first generation.

- **Row counts (`scale=1.0`):** `agents` = `ctx.n(40)`,
  `policyholders` = `ctx.n(4000)`, `policies` = `ctx.n(5000)` (some holders hold
  more than one), `claims` derived from frequency (≈ `ctx.n(1200)`),
  `claim_payments` ≈ 78% of `claims`.
- **annual_premium (tier-driven, right-skew):** preferred median ≈ \$900,
  standard ≈ \$1,300, high_risk ≈ \$2,200 via
  `ctx.dist.lognormal(median, sigma≈0.4)`.
- **coverage_limit / deductible:** limit \$25k–\$300k by product; deductible ∈
  {\$250, \$500, \$1,000} weighted, always `< coverage_limit`.
- **claim frequency (the "frequency" half):** per-policy claim count ~
  `Poisson(λ)` with `λ` scaled by risk tier (preferred ≈ 0.08, standard ≈ 0.15,
  high_risk ≈ 0.35 per year × term). Overall ≈ 12–15% of policies file ≥1 claim.
- **reported_amount (the "severity" half — the headline skew):**
  `ctx.dist.lognormal(median≈2500, sigma≈1.0)` → median ≈ \$2.5k, p95 ≈ \$18k,
  tail past \$50k.
- **claim_date:** uniform within the policy's active window (bounded by
  `start_date` and term), so claims still spread across the ~3-year window.
- **adjudication mix:** approved 0.62 / partial 0.16 / denied 0.14 / open 0.08.
- **paid_amount:** approved = `clip(min(reported, coverage_limit) − deductible, 0,
  None)`; partial = 0.3–0.8 × that; denied/open → no row. `paid_date` = claim date
  + a short settlement delay.
- **loss ratio (Σ paid ÷ Σ premium):** overall ≈ 0.65, ranging preferred ≈ 0.45 →
  high_risk ≈ 0.90.

## Candidate scenarios

- **Frequency-severity: few policies claim, and claim cost is heavy-tailed.**
  Signal: claiming is rare but the payout distribution has a fat right tail.
  Tables: `claims.policy_id`, `claims.reported_amount`,
  `claim_payments.paid_amount`. Target: ≈ 12–15% of policies file a claim; severity
  median ≈ \$2.5k, p95 ≈ \$18k, max past \$50k. How to find it: claim rate =
  `count(distinct policy_id in claims) / count(*) from policies`; then
  `quantile(paid_amount, 0.5/0.95)`, `max(paid_amount)`.

- **Loss ratio rises with risk tier.** Signal: high-risk policies pay out far more
  relative to the premium they bring in. Tables: `claim_payments.paid_amount`,
  `policies.annual_premium`, `policyholders.risk_tier`. Target: overall ≈ 0.65;
  preferred ≈ 0.45 → high_risk ≈ 0.90. How to find it: join
  `payments → claims → policies → policyholders`,
  `sum(paid_amount) / sum(annual_premium)` grouped by `risk_tier`.

- **The adjudication funnel: reported vs paid** (plan-vs-actual). Signal: a chunk of
  claims are denied (\$0), partials pay less than reported, and even approved claims
  net out the deductible — so aggregate paid runs well below aggregate reported.
  Tables: `claims.status`, `claims.reported_amount`, `claim_payments.paid_amount`.
  Target: ≈ 14% denied, ≈ 16% partial; total paid ≈ 60–70% of total reported. How
  to find it: `status` mix from `claims`; `avg(paid_amount / reported_amount)` for
  approved vs partial via a join.

## Realism guidance (seed)

**Invariants — must always hold:**
- Referential integrity: `policies.policyholder_id ∈ policyholders` and
  `policies.agent_id ∈ agents`; `claims.policy_id ∈ policies`;
  `claim_payments.claim_id ∈ claims` with at most one payment per claim, and a
  payment row exists **iff** the claim is `approved` or `partial`.
- Temporal ordering: `claim_date` falls within `[policies.start_date, term end]`
  and the window; `paid_date ≥ claim_date`.
- Payout bounds: `0 ≤ paid_amount ≤ min(reported_amount, coverage_limit) −
  deductible`; a partial pays strictly less than an approved claim would.
- Non-negativity / ordering: `reported_amount > 0`, `annual_premium > 0`,
  `deductible ≥ 0`, `coverage_limit > deductible`.
- Status domain: `claims.status ∈ {open, approved, partial, denied}`.

**Deliberate simplifications — intended, do not "fix":**
- One payout per claim: no reserves, reopenings, or installment settlements.
- Premium is a flat annual figure — no mid-term endorsements or proration on
  cancel/lapse.
- "Loss ratio" is pure paid ÷ premium: no reinsurance, expenses, or investment
  income.
- Peril and severity are independent of policyholder geography and vehicle/home
  specifics.

## Building it

Follows the "Adding a collection" checklist in
[collections/CLAUDE.md](../src/potato_tornado/collections/CLAUDE.md): package
`collections/insurance/` with `__init__.py`, `constants.py`, `tables/`
(`agents`, `policyholders`, `policies`, `claims`, `claim_payments`), `scenarios/`,
`realism-guidance.md`; `register("insurance", build)`; add
`"potato_tornado.collections.insurance"` to `_BUILTIN_MODULES`; README row; tests
mirrored under `tests/collections/insurance/`.

**Core APIs it leans on (all exist today):** `ctx.entities.people` (agents,
policyholders), `ctx.entities.cities`, `ctx.dist.lognormal` / `choice` /
`integers` / `dates_between`, `ctx.n(base)`, `ctx.table(...)`.

**New helpers needed — none.** The claims fan-out from policies uses a **per-policy
Poisson λ** that varies by risk tier; `ctx.dist.poisson(n, lam)` takes a scalar
`lam`, so draw the per-policy counts with `ctx.rng.numpy.poisson(lam_array)`
directly (numpy's Poisson accepts a vector `lam`) rather than adding a vectorized-λ
helper — the same "drop to `ctx.rng.numpy` for a per-row parameter" pattern `labor`
already uses. Only promote a `dist.poisson(lam_array)` overload into
`core/distributions.py` if a second collection needs it.
