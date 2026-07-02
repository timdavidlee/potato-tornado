# Realism log — logistics

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — invariants and the headline distributions have been swept and one
lattice artifact fixed; residual items are documented deliberate simplifications (open items in
`TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Initial build + invariant sweep.** Pinned the hard rules (1:1
  `deliveries`↔`shipments`, terminal-status consistency recovered structurally from the scan
  timeline, strictly increasing `scan_ts` by `seq`, date ordering). Made the `shipping_cost`
  identity *exact* — round `weight_kg` **before** deriving cost so a query can recompute one
  from the other with zero mismatch. (`13793d9`)
- **2026-07-01 — Too-synthetic sweep: de-lattice the terminal scan time.** The terminal
  (delivered/exception) scan previously landed at a single fixed clock time (~18:00), a visible
  time-of-day lattice. Now each shipment's terminal scan draws a time uniformly across
  **[12:00, 20:00)** on the terminal calendar day, so `actual_delivery_date` is unchanged but
  the hour spreads. Guarded by the scan-timestamp note in the rubric. (`e27dc41`)

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (7 quick wins + 5 high-leverage, several scenario-bearing) to [`TODO.md`](TODO.md).
  No columns implemented yet — the backlog is the open work.
