# Realism log — clinic

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — the slot→booking→visit→billing workflow and its planted signals
(lead-time no-shows, duration overrun, self-pay AR) are in place with a realism rubric; residual
items are documented deliberate simplifications (open items in `TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Build + realism docs.** Established the appointment lifecycle
  (completed/no-show/cancelled), the lead-time no-show gradient, per-visit-type duration
  overrun, and the self-pay-concentrated AR, with a realism-guidance rubric. (`b2eeb4e`)

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all six tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a reminder→no-show
  funnel and a payer-adjudication split) to [`TODO.md`](TODO.md). No columns implemented yet —
  the backlog is the open work.
