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

- [ ] **`policyholders.age_band`** (`Utf8`) — `ctx.dist.choice` over {18-25, 26-40, 41-60,
      60+} weighted. Unlocks: demographic slicing of frequency/severity.
- [ ] **`policyholders.tenure_years`** (`Int64`) — `ctx.dist.integers(0, 15)`. Unlocks:
      retention / loyalty analysis; a covariate for renewal.
- [ ] **`policies.payment_frequency`** (`Utf8`) — `ctx.dist.choice` {monthly, quarterly,
      annual}. Unlocks: billing-cadence mix; composes with `annual_premium`.
- [ ] **`policies.channel`** (`Utf8`) — {broker, direct, aggregator} weighted. Unlocks:
      distribution-channel mix (a bought-vs-sold cut alongside `broker_id`).
- [ ] **`claims.reported_channel`** (`Utf8`) — {phone, app, broker, web}. Unlocks: FNOL
      (first-notice-of-loss) channel analysis.
- [ ] **`brokers.tenure_years`** (`Int64`) and **`brokers.commission_rate`** (`Float64`, ~0.08–0.15)
      — per-broker attributes. Unlocks: producer economics (commission on `annual_premium`).

## High-leverage additions

### 1. `policyholders.prior_claims_count`
- [ ] A pre-window claims history count (`Int64`, right-skew via `ctx.dist.poisson`), higher
      for `high_risk`.
- **Unlocks:** experience-rating — does prior history predict in-window frequency?
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: frequency
  rises with `prior_claims_count` within a tier (the actuarial "past predicts future"). Name
  it; don't plant it here.

### 2. `claims.at_fault` / catastrophe flag
- [ ] `at_fault` (`Boolean`, auto only, else null) and `catastrophe_flag` (`Boolean`, correlated
      with the `weather` peril and clustered in time).
- **Unlocks:** cat-vs-attritional loss split; subrogation potential on not-at-fault claims.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: severity
  is far heavier on catastrophe claims (couples severity to a driver — today it's independent,
  a documented realism gap). Route it.

### 3. `claim_payments.adjuster_id` + settlement detail
- [ ] `adjuster_id` (`Utf8`, a small adjuster pool), `settlement_method`
      (`Utf8`: check / ach / card), and `settlement_days` (derivable from `paid_date - claim_date`).
- **Unlocks:** claims-operations analysis — cycle time, adjuster workload.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: settlement
  time or partial-rate varies by adjuster (an operational-outlier subset).

### 4. `policies.renewal_count` + prior-term linkage
- [ ] `renewal_count` (`Int64`, 0 = new business) marking how many times the policy renewed.
- **Unlocks:** new-vs-renewal book split; retention curves; premium drift on renewal.
- **Class:** realism enrichment (a lifecycle dimension). A prior-policy FK (linking successive
  terms) would be a **new relationship**, closer to a schema change — note if pursued.

### 5. `brokers.commission_rate` → producer performance
- [ ] With `commission_rate` (quick win) plus a per-broker `loss_ratio` rollup, the broker dim
      stops being inert.
- **Unlocks:** producer performance — which brokers write profitable business.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: a subset
  of brokers writes systematically higher-loss-ratio business (turns the documented
  "broker/region aggregates are uniform" realism gap into a teachable signal).

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items.

- [ ] **Severity is independent of product, tier, and peril.** A real book couples severity to
      what's insured (a home total-loss dwarfs a renters claim). A severity-by-product cross-tab
      looks suspiciously flat — a candidate coupling (item 2 `catastrophe_flag` above is the
      natural lever).
- [ ] **`coverage_limit` is a 3-value-per-product lattice** (base × {0.5, 1.0, 2.0}) — only 9
      distinct limits across the book. Check whether that discreteness reads as synthetic vs. a
      continuous underwritten limit.
- [ ] **`peril` mix is ~uniform over six perils.** Real peril frequencies are skewed
      (collision/weather common, fire rare). A flat peril histogram is a likely too-synthetic
      flag — a candidate to weight.
- [ ] **Broker/region aggregates are uniform by construction.** `broker_id`/`region` carry no
      signal, so any broker-level roll-up looks flat (item 5 above would turn this into a
      signal).

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
      rubric and invariant tests with the new columns (new dimensions to slice by, new
      invariants — e.g. `at_fault` non-null iff `product = 'auto'`, `settlement_days ≥ 0`).
      Run `/data-collection:review-edit-regen-for-realism` for this collection. Several items
      above would also close the standing realism gap that **severity is independent of
      product/tier/peril** — worth prioritising `catastrophe_flag` severity coupling.
