# insurance — field-enrichment TODO

Candidate columns to add to the existing `insurance` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

Context: a P&C book on a frequency-severity model — `policyholders` (with `risk_tier`) buy
`policies` sold by `brokers`, a minority file `claims`, settled claims get a `claim_payments`
row. The current schema has **no policyholder risk covariates beyond the tier, no broker
economics, no claim context beyond the peril, and no settlement detail** — so severity is
uncoupled from anything, brokers carry no signal, and the adjudication funnel can't be
attributed. The additions below close those gaps.

## Quick wins (realism enrichment)

**All nine shipped 2026-07-02** (see `realism-log.md`) — each drawn off a dedicated
`ctx.rng.child(...)` stream so existing draws stayed byte-identical, all signal-free, invariants
pinned in `test_insurance.py` and reconciled into `realism-guidance.md`.

- [x] **`policyholders.age_band`** (`Utf8`) — child `choice` over {18-25, 26-40, 41-60,
      60+} weighted. Unlocks: demographic slicing of frequency/severity.
- [x] **`policyholders.tenure_years`** (`Int64`) — child `integers(0, 15)`. Unlocks:
      retention / loyalty analysis; a covariate for renewal.
- [x] **`policies.payment_frequency`** (`Utf8`) — child `choice` {monthly, quarterly,
      annual}. Unlocks: billing-cadence mix; composes with `annual_premium`.
- [x] **`policies.channel`** (`Utf8`) — {broker, direct, aggregator} weighted. Unlocks:
      distribution-channel mix (a bought-vs-sold cut alongside `broker_id`).
- [x] **`claims.reported_channel`** (`Utf8`) — {phone, app, broker, web}. Unlocks: FNOL
      (first-notice-of-loss) channel analysis.
- [x] **`brokers.tenure_years`** (`Int64`) and **`brokers.commission_rate`** (`Float64`, 0.08–0.15)
      — per-broker attributes. Unlocks: producer economics (commission on `annual_premium`).
- [x] **`policyholders.state`** (`Utf8`) — child `choice` over a US-state catalog literal
      (50 states + DC, population-weighted). Unlocks: state-level loss ratios and a regulatory
      cut (rates are filed per state) — a coarser, joinable geography than the free-text `city`.
- [x] **`policies.bundled`** (`Boolean`) — **derived, no draw**: true when the holder appears
      on ≥2 `policies` rows. Measured ≈ 0.71 of policies (the 5000/4000 policy-per-holder ratio,
      scale-independent — the earlier "~1.75 policies/holder" estimate was off). Unlocks:
      bundling / cross-sell mix from data already present, no new randomness.
- [x] **`policies.auto_renew`** (`Boolean`) — child `bernoulli(~0.7)`. Unlocks: retention
      posture; composes with `status` (lapsed) and the future `renewal_count`.

## High-leverage additions

### 1. `policyholders.prior_claims_count`
- [x] A pre-window claims history count (`Int64`, right-skew via `ctx.dist.poisson`), higher
      for `high_risk`. **Flat column done 2026-07-11** — `Poisson(0.6)` on its own
      `prior_claims` child stream with a **single tier-independent** λ (measured flat across
      tiers: 0.59 / 0.60 / 0.53), so no experience-rating signal is planted. Pinned
      `test_prior_claims_count_is_non_negative`. The *frequency-rises-with-prior-history*
      signal remains deferred → `/scenario:draft-or-propose`.
- **Unlocks:** experience-rating — does prior history predict in-window frequency?
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: frequency
  rises with `prior_claims_count` within a tier (the actuarial "past predicts future"). Name
  it; don't plant it here.

### 2. `claims.at_fault` / catastrophe flag
- [x] `at_fault` (`Boolean`, auto only, else null) and `catastrophe_flag` (`Boolean`, correlated
      with the `weather` peril and clustered in time). **Flat columns done 2026-07-11** —
      `at_fault` non-null iff product=auto (flat 0.55 among auto), `catastrophe_flag` rate
      conditioned on peril (weather 0.35 / else 0.03, overall ≈ 0.10) with **no** severity
      coupling. Peril draw hoisted to a local (byte-identical); own `at_fault`/`catastrophe`
      child streams. Pinned `test_at_fault_non_null_iff_auto`. The *cat-vs-attritional severity*
      signal remains deferred → `/scenario:draft-or-propose`.
- **Unlocks:** cat-vs-attritional loss split; subrogation potential on not-at-fault claims.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: severity
  is far heavier on catastrophe claims (couples severity to a driver — today it's independent,
  a documented realism gap). Route it.

### 3. `claim_payments.adjuster_id` + settlement detail
- [x] `adjuster_id` (`Utf8`, a small adjuster pool), `settlement_method`
      (`Utf8`: check / ach / card), and `settlement_days` (derivable from `paid_date - claim_date`).
      **Done 2026-07-11** — `settlement_days` = the existing `delay` (derived identity),
      `settlement_method` flat (ach 0.45 / check 0.35 / card 0.20) on its own child stream,
      `adjuster_id` carried from the settled claim (derived FK ∈ adjusters). Pinned
      `test_settlement_days_within_bounds`. The *settlement-time-varies-by-adjuster* signal
      remains deferred → `/scenario:draft-or-propose`.
- **Unlocks:** claims-operations analysis — cycle time, adjuster workload.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: settlement
  time or partial-rate varies by adjuster (an operational-outlier subset).

### 4. `policies.renewal_count` + prior-term linkage
- [x] `renewal_count` (`Int64`, 0 = new business) marking how many times the policy renewed.
      **Done 2026-07-11** — resolved the cold-start tension by scoping it as an **abstract**
      lifecycle marker (`geometric(0.45) − 1`, mode 0, own `renewal_count` child stream)
      **decoupled from `start_date`** (measured corr ≈ 0.01); amended the Cold-start
      simplification to say so. Pinned `test_renewal_count_is_non_negative`. A prior-term FK
      remains a schema change, not pursued.
- **Unlocks:** new-vs-renewal book split; retention curves; premium drift on renewal.
- **Class:** realism enrichment (a lifecycle dimension). A prior-policy FK (linking successive
  terms) would be a **new relationship**, closer to a schema change — note if pursued.
- **Tension (noted 2026-07-02):** a non-zero `renewal_count` implies pre-window terms, which
  sits awkwardly against the documented **Cold-start book** simplification (the in-force grows
  from zero at `start_date`, *no backdated policies*). Either scope it as an abstract lifecycle
  marker uncorrelated with `start_date` (accepting the mild inconsistency, like the flat-annual
  premium), or relax the cold-start note first. Decide before building — this is why it wasn't
  swept in with the quick wins.

### 5. `brokers.commission_rate` → producer performance
- [ ] With `commission_rate` (quick win) plus a per-broker `loss_ratio` rollup, the broker dim
      stops being inert.
- **Unlocks:** producer performance — which brokers write profitable business.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: a subset
  of brokers writes systematically higher-loss-ratio business (turns the documented
  "broker/region aggregates are uniform" realism gap into a teachable signal).

### 6. `claims.fraud_flag` (SIU referral)
- [x] `fraud_flag` / `siu_referral` (`Boolean`, low base rate ~0.03–0.06 via
      `ctx.dist.bernoulli`), tilted toward `theft`/`liability` perils and larger
      `reported_amount`. Buildable today — no new `core/distributions.py` helper needed.
      **Flat column done 2026-07-11** — flat ≈ 0.04 on its own `fraud` child stream, no peril
      or severity tilt. Pinned `test_claim_flag_base_rate[fraud_flag]`. The *flagged-claims-
      deny-more* signal remains deferred → `/scenario:draft-or-propose`.
- **Unlocks:** fraud analytics — a major P&C domain the schema can't touch at all today
      (referral rate, fraud-adjusted loss ratio, the denial funnel by fraud status).
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: flagged
  claims **deny far more often** (an inflated `denied` share) and, when paid, settle lower —
  a surprising subset cut across the existing adjudication funnel. Name it; don't plant it.

### 7. `claims.litigated` (attorney representation)
- [x] `litigated` (`Boolean`, ~0.08–0.12 via `ctx.dist.bernoulli`), concentrated on the
      `liability` peril. Buildable today. **Flat column done 2026-07-11** — flat ≈ 0.10 on its
      own `litigation` child stream, no peril concentration. Pinned
      `test_claim_flag_base_rate[litigated]`. The *litigation-tax* signal (heavier paid_amount +
      longer cycle time) remains deferred → `/scenario:draft-or-propose`.
- **Unlocks:** litigation economics — the "litigation tax" (litigated claims run heavier
      severity and much longer cycle time), a claims-strategy staple.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: litigated
  claims carry materially higher `paid_amount` **and** a longer `paid_date − claim_date` delay
  than non-litigated peers — a subset that couples severity *and* settlement time to one flag.

### Later / depends-on

- [x] **`claims.subrogation_recovery_amount`** (`Float64`, mostly 0 / nullable) — an insurer
      recovery from an at-fault third party, offsetting `paid_amount`. **Depends on item 2's
      `at_fault`** (recovery is only plausible on not-at-fault claims). Unlocks: net-of-subro
      loss ratio (gross paid vs. net paid). **Done 2026-07-11** — built on **`claim_payments`**
      (where `paid_amount` and, via the settled join, `at_fault` are both visible): positive
      recovery only on not-at-fault claims (25% of eligible, ≈ 5–6% of payments), amount
      0.20–0.60× `paid_amount` so recovery ≤ paid_amount, null on ineligible / 0.0 on
      eligible-unrecovered. Own `subrogation` + `subrogation_amount` child streams. Pinned
      `test_subrogation_recovery_only_on_not_at_fault`.

## Candidate new tables (within this collection)

New tables that join into `insurance` (a new entity or event + its FK into an existing table),
sketch-level — enough to act on, not a full column spec. A whole new *collection* (e.g. a
standalone reinsurance domain) is `/data-collection:propose`'s job, not this. All buildable from
existing `ctx` primitives — no new `core/distributions.py` helper.

- [x] **`adjusters`** — **implemented 2026-07-02** (see `realism-log.md`). A 40-row handler dim
      (`adjuster_id`, `full_name`, `email`, `team`, `seniority`) + a uniform `claims.adjuster_id`
      FK. Assignment is signal-free (realism enrichment). The **scenario-bearing** angle — a
      handler/team settling slower or partialing more — was *not* planted; it remains a
      candidate for `/scenario:draft-or-propose`.
- [x] **`quotes`** — **implemented 2026-07-02** (see `realism-log.md`). One converting quote per
      policy + non-converting shopping quotes (`converted` ≈ 0.40), nullable `policy_id` FK.
      Conversion is signal-free (flat vs premium/product). The **scenario-bearing** funnel —
      conversion falling with `quoted_premium` / varying by `product` — was *not* planted; it
      remains a candidate for `/scenario:draft-or-propose`.

### `premium_billing`
- [x] **`premium_billing`** — **implemented 2026-07-02** (see `realism-log.md`). One row per
      instalment (`billing_id`, `policy_id`, `installment_number`, `due_date`, `amount`,
      `status`, nullable `paid_date`); N per policy by `payment_frequency` (12 / 4 / 1), amounts
      **sum to `annual_premium`** to the cent (last instalment absorbs the rounding remainder).
      `status` (paid 0.90 / late 0.07 / missed 0.03) is **signal-free** — the concentrating
      delinquency funnel (monthly-pay / high_risk miss more) was *not* planted; it remains a
      candidate for `/scenario:draft-or-propose`. Drawn off its own name-keyed `premium_billing`
      streams, so every other table stays byte-identical. Pinned 8 invariant tests (FK, the
      sum-to-premium identity, count-by-cadence, `paid_date` null-iff-missed, date ordering).

### Tables that would require revisiting a deliberate simplification

These model real P&C structure but **contradict a documented Deliberate simplification** in
`realism-guidance.md` — noted here (not proposed blindly) so the tension is a conscious call,
not a surprise. Each needs that simplification relaxed first.

- [x] **`claim_status_history`** (one row per claim status transition:
      reported → under_review → approved/partial/denied, with timestamps). Contradicts *"one
      payout per claim … adjudicated once to a single terminal status"* and *"no reopenings"*.
      Would unlock claim-lifecycle / cycle-time-between-stages analytics. Relax the single-status
      simplification before building. **Done 2026-07-11** — 3 transition rows/claim
      (`reported → under_review → claims.status`), terminal `to_status` == `claims.status`,
      strictly-increasing `changed_at` from `claim_date`, own `status_history` child stream (no
      pre-existing column shifted). Relaxed the single-terminal-status simplification while
      keeping the no-reopening/one-payout guarantee. Pinned
      `test_status_history_terminal_matches_claim_status`. The cycle-time-varies-by-slice signal
      remains a scenario candidate → `/scenario:draft-or-propose`.
- [x] **`coverage_lines`** (one row per coverage line on a policy — e.g. auto's liability /
      collision / comprehensive, each with its own limit, deductible, and premium share).
      Contradicts *"coverage_limit takes a small set of values"* and the single-limit payout
      arithmetic, and reworks how a claim maps to a covered line. High value (line-level loss
      ratios) but a deep change to the payout model. **Done 2026-07-11 as a MINIMAL ADDITIVE
      (premium-side) breakdown** — the 10th insurance table, one row per line per policy
      (`COVERAGE_LINES` catalog in `constants.py`). `line_premium_share` **sums to
      `annual_premium`** to the cent (last line absorbs the remainder); `line_limit` = catalog
      base × lognormal jitter rounded to \$100 (near-continuous, relaxing the lattice at the
      **line grain only** — the policy-level `coverage_limit` lattice stays because payout reads
      it); `line_deductible` = policy deductible where it applies, 0 on liability. Reads only
      `policies`, off its own `coverage_split` / `coverage_limit_jitter` streams, so every
      pre-existing table is byte-identical (`seed=7, scale=0.3`). **The payout path is NOT
      rewired** — no claim maps to a line, `line_limit` is deliberately not reconciled against
      `coverage_limit`. Pinned `test_coverage_line_shares_sum_to_annual_premium`; reconciled the
      rubric (invariant + distribution + row-count lines, relaxed the lattice bullet, added a
      "payout stays policy-level" simplification). **Line-level loss ratios** (map a claim's
      peril to its covered line, price against `line_limit`) remain a deferred scenario →
      `/scenario:draft-or-propose`.
- [ ] **`reinsurance_treaties`** + ceded-loss allocation. Contradicts *"loss ratio is pure paid
      ÷ premium — no reinsurance"*, and is arguably its own domain (net-vs-gross, cessions) —
      closer to a **new collection** (→ `/data-collection:propose`) than an in-collection table.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items.

- [ ] **Severity is independent of product, tier, and peril.** A real book couples severity to
      what's insured (a home total-loss dwarfs a renters claim). A severity-by-product cross-tab
      looks suspiciously flat. **Evaluated 2026-07-02 — left as a deliberate simplification**
      (documented in the rubric); the coupling is scenario work, not a realism fix — item 2
      `catastrophe_flag` is the natural lever → `/scenario:draft-or-propose`.
- [ ] **`coverage_limit` is a 3-value-per-product lattice** (base × {0.5, 1.0, 2.0}) — only 7
      distinct limits across the book. **Evaluated 2026-07-02 — left as a deliberate
      simplification** ("keeps the payout arithmetic legible", per the rubric); not fixed.
- [x] **`peril` mix is ~uniform over six perils.** **Fixed 2026-07-02** (see `realism-log.md`):
      weighted to a skewed personal-lines marginal (collision 0.28 … fire 0.06), off a dedicated
      `peril` child stream; peril stays independent of product/geography. Pinned
      `test_peril_mix_is_skewed_not_uniform`.
- [ ] **Broker/region aggregates are uniform by construction.** `broker_id`/`region` carry no
      signal, so any broker-level roll-up looks flat. **Evaluated 2026-07-02 — left as a
      deliberate simplification** ("carries no signal"); turning it into a signal is item 5's
      producer-performance scenario, not a realism fix.
- [x] **`brokers.tenure_years` is uniform over [1, 30].** **Fixed 2026-07-11** — geometric
      decay (ratio 0.90) over [1, 30] on the same `tenure` child stream (only that column
      moved; mean ≈ 8.5, newer producers outnumber ≥20yr veterans, no boundary pile). Pinned
      `test_broker_tenure_is_right_skewed`.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
      rubric and invariant tests with the new columns (new dimensions to slice by, new
      invariants — e.g. `at_fault` non-null iff `product = 'auto'`, `settlement_days ≥ 0`).
      Run `/data-collection:review-edit-regen-for-realism` for this collection. Several items
      above would also close the standing realism gap that **severity is independent of
      product/tier/peril** — worth prioritising `catastrophe_flag` severity coupling.
