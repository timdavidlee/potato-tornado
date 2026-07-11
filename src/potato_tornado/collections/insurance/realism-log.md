# Realism log — insurance

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — four passes fixed an end-of-window claim pile-up, a flat premium
sub-population, a uniform peril histogram, and uniform policyholder tenure; the remaining
open-realism items are documented deliberate simplifications (severity independence — a scenario
candidate — the coverage lattice, and broker/region inertness), plus one low-priority residual
(uniform broker tenure, a 40-row dim). (as of 2026-07-02)

## Realism iterations

- **2026-07-11 — New table: `coverage_lines` (per-policy coverage breakdown).** Added the 10th
  insurance table — one row per coverage line per policy (auto: liability / collision /
  comprehensive; home: dwelling / contents / liability; renters: contents / liability, from the
  new `COVERAGE_LINES` catalog in `constants.py`). Built as a **minimal additive, premium-side**
  breakdown: `line_premium_share` splits `annual_premium` around the catalog base weights with a
  per-line lognormal jitter (σ ≈ 0.25) and **sums back to `annual_premium`** to the cent (last
  line absorbs the remainder, the same identity as `premium_billing`); `line_limit` = catalog
  base × lognormal jitter (σ ≈ 0.15) rounded to \$100 — near-continuous (~1,400 distinct values),
  relaxing the coverage lattice **at the line grain only**; `line_deductible` = the policy
  deductible where the line carries one, 0 on liability lines (derived). Reads only `policies`,
  off its own `coverage_split` / `coverage_limit_jitter` child streams, so every pre-existing
  table stayed **byte-identical** (`seed=7, scale=0.3`; ~14,000 lines at scale 1.0). **The claim →
  payout path was deliberately NOT rewired** — no claim maps to a line, claims still price against
  the policy-level `coverage_limit`/`deductible`, and `line_limit` is not reconciled against
  `coverage_limit`. This **partly relaxes** the "coverage_limit takes a small set of values"
  simplification (line grain only) and **adds** a "payout stays policy-level" simplification;
  line-level loss ratios remain a deferred scenario. Pinned
  `test_coverage_line_shares_sum_to_annual_premium`; reconciled the rubric (a coverage-lines
  invariant block, a split distribution line, the row-count line, the relaxed lattice bullet, and
  the new payout-stays-policy-level bullet) and the README table row.
- **2026-07-11 — New table: `claim_status_history` (lifecycle transitions).** Added the 9th
  insurance table — 3 rows per claim walking `reported → under_review → the claim's status`,
  with `changed_at` starting at `claim_date` and strictly increasing per stage (own
  `status_history` child stream; two gap draws). The terminal (`seq = 3`) `to_status` **equals**
  `claims.status`, so the log reconciles with `claims` exactly. Adding the table left every
  pre-existing column byte-identical (`seed=7, scale=0.3`). This **relaxes** the "adjudicated
  once, no transition log" simplification — the transitions are now modelled — while keeping the
  single-terminal-state / no-reopening / one-payout guarantee. Pinned
  `test_status_history_terminal_matches_claim_status`; reconciled the rubric (a status-history
  invariant block, the row-count line, the relaxed simplification, and two How-to-review
  queries).
- **2026-07-11 — Subrogation recovery on `claim_payments`.** Added
  `subrogation_recovery_amount` where both `paid_amount` and (via the settled join)
  `at_fault` are visible. Positive **only** on not-at-fault claims (gated on `at_fault is
  False`): ≈ 25% of eligible auto claims recover (≈ 0.055 of all payments), amount 0.20–0.60×
  `paid_amount` so recovery ≤ paid_amount; null on ineligible (at-fault / non-auto) and 0.0 on
  eligible-unrecovered. Own `subrogation` + `subrogation_amount` streams; every pre-existing
  column byte-identical (`seed=7, scale=0.3`). Enables a net-of-subro loss ratio. Pinned
  `test_subrogation_recovery_only_on_not_at_fault`; reconciled the rubric (a subrogation
  eligibility invariant + an occurrence/amount distribution line).
- **2026-07-11 — Settlement detail on `claim_payments`.** Added `settlement_days` (derived =
  the existing 5–45 day settle delay, so `settlement_days = paid_date − claim_date`),
  `settlement_method` (flat ach 0.46 / check 0.35 / card 0.20 on its own child stream), and a
  carried `adjuster_id` (the settled claim's handler, a derived FK ∈ adjusters — no draw). Only
  the three new columns appeared; every pre-existing column stayed byte-identical
  (`seed=7, scale=0.3`). All flat — no per-adjuster / per-amount coupling, so a
  cycle-time-by-adjuster roll-up is deliberately flat (deferred scenario). Pinned
  `test_settlement_days_within_bounds`; reconciled the rubric (adjuster-FK + settlement-days
  identity invariants, a settlement-method catalog + mix line, the `adjuster_id` simplification).
- **2026-07-11 — Claim-context flags: `at_fault` / `catastrophe_flag` / `fraud_flag` /
  `litigated`.** Added four claim flags to `claims`, each **flat** off its own child stream.
  `at_fault` (flat 0.55) is non-null **iff** the policy product is auto, else null;
  `catastrophe_flag` (≈ 0.10) conditions only its *rate* on the weather peril (0.35 vs 0.03) —
  severity stays peril-independent; `fraud_flag` ≈ 0.046 and `litigated` ≈ 0.109 are flat base
  rates. The existing `peril` draw was **hoisted to a local** (same stream/call) so
  `catastrophe_flag` can read it without a second draw and every pre-existing column stays
  byte-identical (`seed=7, scale=0.3`). No severity/tier/adjuster coupling — the
  cat-vs-attritional severity split, fraud-denies-more, and litigation-tax signals are deferred
  scenario candidates. Pinned `test_at_fault_non_null_iff_auto` and
  `test_claim_flag_base_rate` (fraud + litigated); reconciled the rubric (an `at_fault`-nullity
  invariant, a claim-flags distribution line, and a claim-flags simplification bullet).
- **2026-07-11 — Flat covariate: `policyholders.prior_claims_count`.** Added a pre-window
  claims-history count as a right-skewed `Poisson(0.6)` (mode 0, mean ≈ 0.59, max ~5) on its
  own `prior_claims` child stream (every other column byte-identical at `seed=7, scale=0.3`).
  Kept **flat** — a single tier-independent λ (measured means 0.59 / 0.60 / 0.53 across
  preferred / standard / high_risk), so **experience rating** is deliberately absent and
  documented as a candidate scenario. Pinned `test_prior_claims_count_is_non_negative`;
  reconciled the Holder-demographics distribution line and the enrichment simplification.
- **2026-07-11 — Lifecycle marker: `policies.renewal_count`.** Added the new-vs-renewal book
  dimension (`geometric(0.45) − 1`, mode 0 ≈ 0.45, mean ≈ 1.2, always ≥ 0) on its own
  `renewal_count` child stream so every existing column stayed byte-identical
  (`seed=7, scale=0.3`). Resolved the long-standing cold-start tension by scoping it as an
  **abstract** marker **decoupled from `start_date`** (measured corr ≈ 0.01) rather than a
  real prior-term history; amended the Cold-start deliberate-simplification bullet to record
  that call. Pinned `test_renewal_count_is_non_negative`.
- **2026-07-11 — Too-synthetic sweep: uniform broker tenure.** Cleared the last open
  realism residual: `brokers.tenure_years` was drawn **uniformly** over [1, 30]
  (`integers(1, 31)`). Replaced it with geometrically-decaying weights (ratio 0.90) over the
  same [1, 30] support via `choice` on the **same** `tenure` child stream, so only that
  column moved (verified byte-identical elsewhere at `seed=7, scale=0.3`): mean ≈ 8.5, newer
  producers (≤5yr) outnumber ≥20yr veterans, monotonic taper to 30 (no boundary pile). Pinned
  `test_broker_tenure_is_right_skewed` (full scale, 40-row dim) and reconciled the rubric's
  Broker-attributes line.
- **2026-07-02 — Too-synthetic sweep: uniform policyholder tenure.** A follow-up sweep of the
  enrichment columns caught `policyholders.tenure_years` drawn **uniformly** over [0, 15] (flat
  ~0.06 each, mean ≈ 7.5) — real customer tenure in a growing book is right-skewed. Replaced the
  uniform draw with geometrically-decaying weights (ratio 0.85) over the same [0, 15] support:
  mean ≈ 4.2, median 3, ~0.53 of holders ≤ 3 yr, monotonic taper to 15 (no boundary pile). Drawn
  on the same isolated `tenure` child stream, so every other table stays byte-identical. Pinned
  `test_policyholder_tenure_is_right_skewed` and reconciled the rubric. Same sweep confirmed
  premium-by-channel, severity-by-age_band, and billing-missed-rate-by-cadence are all flat as
  documented (signal-free). **Broker `tenure_years` is also uniform** but left as-is — a 40-row
  dim where the shape is not a strong tell (noted in `TODO.md`).
- **2026-07-02 — Too-synthetic sweep: uniform peril mix.** The `peril` histogram was flat
  (`ctx.dist.choice` with no weights, ≈ 0.167 each — and `fire`, which should be rare, was the
  *most* common at 0.20). Weighted it to a skewed personal-lines marginal (collision 0.28 /
  water_damage 0.22 / weather 0.20 / theft 0.14 / liability 0.10 / fire 0.06), drawn off a
  dedicated `peril` child stream. Peril stays independent of product/geography (unchanged
  deliberate simplification) — only the marginal shape moved. The status draw reshuffled off the
  parent stream but the adjudication mix and per-tier loss ratios held within seed noise
  (approved ≈ 0.63, loss ratio 0.39 → 0.62 → 0.81). Pinned `test_peril_mix_is_skewed_not_uniform`
  and reconciled the rubric's peril line. Swept and judged deliberate (left as-is): flat
  severity-by-product (a scenario candidate — `catastrophe_flag`), the 7-value coverage lattice,
  and the ~uniform broker region.
- **2026-07-01 — Initial build + frequency/severity/loss-ratio self-consistency.** The
  proposal's targets (12% frequency, \$2.5k severity, \$1.3k premium → 0.65 loss ratio) were
  internally inconsistent (that mix yields ~0.26). Held premium and frequency on their
  realistic targets and raised severity so the loss ratio lands ~0.6–0.68 overall and rises
  with tier. Pinned invariants (payment-iff-settled, payout bounds, date ordering). (`13793d9`)
- **2026-07-01 — Too-synthetic sweep: claim timing + flat premium.** (a) Claim counts now scale
  with each policy's **in-window exposed span** (term clipped to `end_date`), not the full
  contractual term — removed a pile-up of claims at the window end (regression-guarded by
  `test_claims_not_piled_at_window_end`). (b) Premium was previously constant within a
  product+tier cell; added a **weak** premium↔coverage (+) / premium↔deductible (−) co-movement
  (centred on the weighted mean so tier medians are unchanged), so the sub-population is no
  longer flat. Both documented in the rubric. (`e27dc41`, `4233197`)
- **2026-07-02 — Two new tables from the backlog: `adjusters` + `quotes`.** Realised the two
  clean-joining candidates from `TODO.md`. `adjusters` — a 40-row claims-handler dim, with a
  **uniform** `claims.adjuster_id` FK drawn from a dedicated `child("adjuster")` stream so the
  existing peril/status draws (and all claim/payment numerics) stay byte-identical. `quotes` —
  an upstream sales stage: one converting quote per policy (priced within ±5% of the bound
  premium, `quote_date ≤ start_date`) plus non-converting shopping quotes to a ~**0.40**
  conversion rate, nullable `policy_id` FK. Both assignments are **signal-free** (adjuster load
  flat; conversion flat vs premium/product) — the operational and funnel signals are left as
  scenario candidates, not planted. Pinned 8 invariant tests (referential integrity, `converted`
  ⇔ `policy_id`, one-quote-per-policy, quote precedes start, conversion rate) and reconciled the
  rubric (row counts, catalogs, the two "carries no signal" simplifications).

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a broker
  producer-performance signal and a `catastrophe_flag` severity coupling) to
  [`TODO.md`](TODO.md). No columns implemented yet — the backlog is the open work.
- **2026-07-02 — Field-enrichment survey (follow-up curation).** Re-checked the live schema
  against the backlog and added the two P&C domains it was missing — **fraud / SIU referral**
  (`claims.fraud_flag`) and **litigation** (`claims.litigated`), both scenario-bearing — plus
  three compositional quick wins (`policyholders.state`, a derivable `policies.bundled`,
  `policies.auto_renew`) and a `subrogation_recovery_amount` item gated on `at_fault`. Backlog
  now 9 quick wins + 7 high-leverage; still nothing implemented. All buildable from existing
  `ctx` primitives (`bernoulli` / `choice`) — no new `core/distributions.py` helper required.
- **2026-07-02 — New-table survey.** First pass of the extended
  `/data-collection:suggest-analytic-fields` (now also proposes new tables *within* the
  collection). Added a **Candidate new tables** section to [`TODO.md`](TODO.md): three
  clean-joining tables — **`adjusters`** dim (promotes the existing `adjuster_id` column idea;
  claims-ops signal), **`quotes`** fact (quote-to-bind funnel), and **`premium_billing`**
  instalments (delinquency; sums to `annual_premium`) — all buildable with existing `ctx`
  primitives. Plus three flagged as **contradicting a deliberate simplification** (not proposed
  blindly): `claim_status_history` (vs one-payout-per-claim), `coverage_lines` (vs the
  single-limit payout arithmetic), and `reinsurance_treaties` (vs pure paid÷premium; closer to
  a new collection). Nothing implemented — the backlog is the open work.
- **2026-07-02 — Quick-win enrichment: all 9 fields shipped.** Cleared the entire "Quick wins"
  block of `TODO.md` in one pass. Added `policyholders.{state, age_band, tenure_years}`,
  `policies.{channel, payment_frequency, auto_renew, bundled}`, `brokers.{tenure_years,
  commission_rate}`, and `claims.reported_channel`. `state` is population-weighted over 50
  states + DC; `bundled` is **derived** (holder on ≥2 policies, ≈ 0.71 of policies, no draw);
  every other field draws off a **dedicated `ctx.rng.child(...)` stream**, so all existing
  premium / claim / quote numerics stay byte-identical and the scenario magnitudes are
  untouched. All fields are **signal-free** (independent of frequency/severity/premium/outcome)
  — the demographic, channel, and producer-economics signals remain scenario candidates.
  Pinned 8 invariant tests (catalog membership, bounded ranges, `bundled` derivation) and
  reconciled `realism-guidance.md` (catalogs, mixes, a "carries no signal" simplification).
- **2026-07-02 — New table: `premium_billing` (instalment schedule).** Realised the
  `premium_billing` candidate from `TODO.md` (8th insurance table). One row per instalment,
  N by `payment_frequency` (12 / 4 / 1), amounts **sum to `annual_premium`** to the cent (the
  last instalment absorbs the rounding remainder — an arithmetic identity pinned in a test).
  `status` (paid 0.90 / late 0.07 / missed 0.03) and the on-time/late payment lag are
  **signal-free**, drawn off dedicated `premium_billing` child streams so every other table
  stays byte-identical. Composes with the `payment_frequency` quick-win and **decomposes** the
  flat annual premium without contradicting it (documented as a refinement, not a re-rating).
  Pinned 8 invariant tests; reconciled `realism-guidance.md` (row count, an invariants block, a
  billing-mix line, two simplifications) and the README table row. The concentrating-delinquency
  funnel remains a scenario candidate. Also flagged a **cold-start tension** on the still-open
  `renewal_count` item in `TODO.md` (pre-window terms vs. the no-backdated-policies simplification).
