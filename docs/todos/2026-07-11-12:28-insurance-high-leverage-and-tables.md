# Insurance high-leverage columns + candidate tables — task list

- **Created:** 2026-07-11 12:28
- **Scope:** the `insurance` collection only.
- **Source:** [`collections/insurance/TODO.md`](../../src/potato_tornado/collections/insurance/TODO.md)
  — the authoritative backlog. This file is a working checklist extracted from it; keep the two
  in step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/insurance/realism-log.md)).
- **Status:** all **9 quick wins** shipped (2026-07-02), and three signal-free tables built
  (`adjusters`, `quotes`, `premium_billing`). Open: the **7 high-leverage columns** (mostly
  scenario-bearing), the **subrogation** follow-on, and **3 candidate tables** that each require
  relaxing a documented simplification first. Realism residuals below are already evaluated.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism insurance`
  (build the column/table flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset signal*
  goes through `/scenario:draft-or-propose insurance` then `/scenario:review-and-edit-regenerate`.
  Don't plant the signal during the realism pass.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` / `ctx.entities`
on a **name-keyed child stream** without reordering existing draws; reconcile the matching line in
`realism-guidance.md`; add/extend an invariant test in
`tests/collections/insurance/test_insurance.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## High-leverage columns

- [ ] **`policyholders.prior_claims_count`** (`Int64`)
  - File: `tables/policyholders.py`. Draw: pre-window history, right-skew via `ctx.dist.poisson`,
    higher for `high_risk`; own child stream.
  - Unlocks: experience-rating — does prior history predict in-window frequency?
  - Class: **scenario-bearing** → *frequency rises with `prior_claims_count` within a tier*.

- [ ] **`claims.at_fault`** (`Boolean`, auto only else null) + **`claims.catastrophe_flag`** (`Boolean`)
  - File: `tables/claims.py`. Draw: `at_fault` for auto; `catastrophe_flag` correlated with the
    `weather` peril and clustered in time; own child stream.
  - Unlocks: cat-vs-attritional loss split; subrogation potential on not-at-fault claims.
  - Class: **scenario-bearing** → *severity is far heavier on catastrophe claims* — the natural
    lever to close the standing "severity independent of product/tier/peril" gap.

- [ ] **`claim_payments` settlement detail** — `settlement_method` (`Utf8`: check/ach/card) +
  `settlement_days` (`paid_date − claim_date`), and an adjuster linkage on payments
  - File: `tables/claim_payments.py`. Draw: own child stream; `settlement_days` is derived.
    (The `adjusters` dim + `claims.adjuster_id` FK already exist — reuse them.)
  - Unlocks: claims-operations analysis — cycle time, adjuster workload.
  - Class: **scenario-bearing** → *settlement time or partial-rate varies by adjuster*.

- [ ] **`policies.renewal_count`** (`Int64`, 0 = new business) — ⚠ decide the cold-start tension first
  - File: `tables/policies.py`. Draw: a lifecycle marker; own child stream.
  - Unlocks: new-vs-renewal book split; retention curves; premium drift on renewal.
  - Class: **realism** (lifecycle dimension).
  - ⚠ **Tension:** a non-zero count implies pre-window terms, which sits against the documented
    **Cold-start book** simplification. Either scope it as an abstract marker uncorrelated with
    `start_date`, or relax the cold-start note first — decide before building. A prior-term FK
    would be a schema change, not a column.

- [ ] **`brokers` producer performance** — a per-broker `loss_ratio` rollup on top of the shipped
  `commission_rate`
  - File: `tables/brokers.py` (+ a rollup). Draw: turns the inert broker dim into a signal.
  - Unlocks: producer performance — which brokers write profitable business.
  - Class: **scenario-bearing** → *a subset of brokers writes systematically higher-loss-ratio
    business* (turns the "broker/region aggregates are uniform" gap into a taught signal).

- [ ] **`claims.fraud_flag`** / `siu_referral` (`Boolean`, base ~0.03–0.06)
  - File: `tables/claims.py`. Draw: `ctx.dist.bernoulli`, tilted toward `theft`/`liability` perils
    and larger `reported_amount`; own child stream. No new `core/distributions.py` helper needed.
  - Unlocks: fraud analytics — referral rate, fraud-adjusted loss ratio, denial funnel by status.
  - Class: **scenario-bearing** → *flagged claims deny far more often and, when paid, settle lower*.

- [ ] **`claims.litigated`** (`Boolean`, ~0.08–0.12)
  - File: `tables/claims.py`. Draw: `ctx.dist.bernoulli`, concentrated on the `liability` peril;
    own child stream.
  - Unlocks: litigation economics — the "litigation tax" (heavier severity, longer cycle time).
  - Class: **scenario-bearing** → *litigated claims carry higher `paid_amount` and a longer
    `paid_date − claim_date` delay* than non-litigated peers.

- [ ] **`claims.subrogation_recovery_amount`** (`Float64`, mostly 0 / nullable) — **depends on
  `at_fault`**
  - File: `tables/claims.py`. Draw: an insurer recovery, plausible only on not-at-fault claims;
    own child stream. Build after item 2's `at_fault` exists.
  - Unlocks: net-of-subro loss ratio (gross paid vs. net paid).
  - Class: **realism** (once `at_fault` exists).

## Candidate new tables (within the collection)

Each needs a new `tables/<table>.py` builder + a `TableSpec` (with `depends_on`) in `__init__.py`.
No `core/registry.py` change (same package). **Each contradicts a documented Deliberate
simplification** — relax it in the same change, not blindly.

- [ ] **`claim_status_history`** — one row per claim status transition (reported → under_review →
  approved/partial/denied, with timestamps). Contradicts *"one payout per claim … a single
  terminal status"* and *"no reopenings"*. Unlocks claim-lifecycle / cycle-time-between-stages.
  Relax the single-status simplification first. Class: **realism** (scenario-bearing once cycle
  time varies by a slice).
- [ ] **`coverage_lines`** — one row per coverage line on a policy (auto's liability / collision /
  comprehensive, each with its own limit, deductible, premium share). Contradicts *"coverage_limit
  takes a small set of values"* and the single-limit payout arithmetic. High value (line-level
  loss ratios) but a deep change to the payout model. Class: **realism** (schema-deep).
- [ ] **`reinsurance_treaties`** + ceded-loss allocation. Contradicts *"loss ratio is pure paid ÷
  premium — no reinsurance"*, and is arguably its own domain — closer to a **new collection**
  (→ `/data-collection:propose`) than an in-collection table. Decide scope before building.

## Open realism items to investigate

Mostly **already evaluated 2026-07-02** and documented as deliberate simplifications (severity
independent of product/tier/peril; the 3-value `coverage_limit` lattice; uniform broker/region
aggregates) — revisit only via the scenario items above, not as realism fixes. One live residual:

- [ ] **`brokers.tenure_years` is uniform over [1, 30].** Low-priority; only a 40-row dim, so the
  flat shape is a weak tell. Right-skew it if the broker dim ever grows or gains analytic weight.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** Reconcile the rubric and invariant tests with the new
  columns (e.g. `at_fault` non-null iff `product = 'auto'`, `settlement_days ≥ 0`). Prioritise
  `catastrophe_flag` severity coupling — it closes the standing severity-independence gap.

---

## Suggested order

1. **`claims.fraud_flag` and `claims.litigated`** — buildable today, no dependencies, each a clean
   flat column then a high-value scenario.
2. **`claims.at_fault` + `catastrophe_flag`** — closes the severity-independence realism gap; then
   `subrogation_recovery_amount` follows.
3. **`policyholders.prior_claims_count`** and **`claim_payments` settlement detail** — experience-
   rating and claims-ops, each scenario-bearing.
4. **`policies.renewal_count`** — resolve the cold-start tension first.
5. **Candidate tables** (`claim_status_history`, then `coverage_lines`; `reinsurance_treaties` only
   if scoped as its own domain) — each relaxes a simplification, so do them deliberately, last.
