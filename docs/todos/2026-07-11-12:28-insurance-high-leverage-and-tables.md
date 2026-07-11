# Insurance — dated working checklist (2026-07-11 12:28)

- **Scope:** the `insurance` collection only.
- **Source of truth:** [`collections/insurance/TODO.md`](../../src/potato_tornado/collections/insurance/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/insurance/realism-log.md). Workflow lives
  in [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** quick wins already shipped. This run (2026-07-11) built the high-leverage columns
  flat + `claim_status_history`; `coverage_lines` and `reinsurance_treaties` deferred, and the
  planted signals route to `/scenario:draft-or-propose`.

## Checklist

**High-leverage columns** (scenario-bearing built flat) **→** [`TODO.md` § High-leverage additions](../../src/potato_tornado/collections/insurance/TODO.md#high-leverage-additions)

- [x] `policyholders.prior_claims_count` *(2026-07-11 — flat)*
- [x] `claims.at_fault` + `catastrophe_flag` *(2026-07-11 — flat)*
- [x] `claim_payments` settlement detail (`settlement_method` / `settlement_days` / `adjuster_id`) *(2026-07-11)*
- [x] `policies.renewal_count` *(2026-07-11 — abstract marker)*
- [ ] `brokers` producer `loss_ratio` rollup *(scenario-bearing → routed)*
- [x] `claims.fraud_flag` *(2026-07-11 — flat)*
- [x] `claims.litigated` *(2026-07-11 — flat)*
- [x] `claims.subrogation_recovery_amount` *(2026-07-11)*

**Candidate new tables →** [`TODO.md` § Candidate new tables](../../src/potato_tornado/collections/insurance/TODO.md#candidate-new-tables-within-this-collection)

- [x] `claim_status_history` *(2026-07-11)*
- [x] `coverage_lines` *(2026-07-11 — minimal additive premium-side breakdown; payout not rewired)*
- [ ] `reinsurance_treaties` *(deferred → `/data-collection:propose`)*

**Open realism items →** [`TODO.md` § Open realism items to investigate](../../src/potato_tornado/collections/insurance/TODO.md#open-realism-items-to-investigate)

- [x] `brokers.tenure_years` uniform → right-skew *(2026-07-11)*

**When the list is done →** [`TODO.md` § When the list is done](../../src/potato_tornado/collections/insurance/TODO.md#when-the-list-is-done)

- [ ] Revise `realism-guidance.md` (reconciled per column as each landed)
