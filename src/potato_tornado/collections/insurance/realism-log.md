# Realism log — insurance

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — two passes fixed an end-of-window claim pile-up and a flat premium
sub-population; residual items are documented deliberate simplifications (open items in
`TODO.md`). (as of 2026-07-02)

## Realism iterations

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

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a broker
  producer-performance signal and a `catastrophe_flag` severity coupling) to
  [`TODO.md`](TODO.md). No columns implemented yet — the backlog is the open work.
