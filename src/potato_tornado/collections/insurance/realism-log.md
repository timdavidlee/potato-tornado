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
