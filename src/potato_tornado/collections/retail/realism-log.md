# Realism log — retail

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Needs investigation** — invariants and the planted category signals are solid, but
**no dedicated too-synthetic sweep has run yet**; several dimensions are likely too clean (open
items in `TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Initial build + basket-value price re-tune.** Pinned the invariants
  (header/line fan-out consistency `item_count == #order_items`, `line_total` identity,
  `refund ≤ line_total`, `order_date ≥ signup`, `return_date ≥ order_date`). Lowered the
  per-category price medians so `unit_price` median ≈ \$22 and basket value median ≈ \$80 (the
  proposal's \$35 basket was inconsistent with a \$22 item median × ~2.5 items). Verified the
  category return-rate gradient (2% → 22%) and category-specific reason mixes. (`13793d9`)

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all five tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a `products.cost`
  margin signal) to [`TODO.md`](TODO.md). No columns implemented yet — the backlog is the open
  work.
