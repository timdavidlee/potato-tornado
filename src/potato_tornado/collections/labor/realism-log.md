# Realism log — labor

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — the worked reference collection; audited with invariant tests, and
residual flat dimensions are documented deliberate simplifications (most tagged as *future
scenarios*, i.e. signals to plant, not realism defects; open items in `TODO.md`). (as of
2026-07-02)

## Realism iterations

- **2026-07-01 — Realism audit + invariant tests.** Cross-checked referential integrity, the
  no-show ⇔ null-clocks rule, `worked ≥ planned` overtime, the pay/bill ladders, and the
  off-site-by-location gradient; added invariant tests. (`8ffba28`)
- **2026-07-01 — Realism-pass tuning.** Distribution/weight tuning across the enrichment
  columns (attendance-by-window, overtime concentration, project staffing). (`e27dc41`)

## Field-enrichment runs

- **2026-07-01 — Field-enrichment survey + full build (backlog complete).** 20 columns across
  all tables: quick wins (`projects.client_name` / `.industry` / `.billing_type` / `.priority`,
  `employees.weekly_capacity_hours` / `.primary_skill` / `.work_mode`,
  `departments.practice_type`); the margin/realization chain (`employees.standard_bill_rate`,
  `project_members.bill_rate`); the utilization chain (`employees.is_billable` /
  `.target_utilization_pct`, `time_entries.billable`); and the project-economics batch
  (`projects.budget_hours` / `.budget_amount` / `.actual_end_date` / `.client_satisfaction`).
  Each reconciled `realism-guidance.md` + invariant tests. Full record in [`TODO.md`](TODO.md).
  (`13793d9`)
- **2026-07-11 — Round-2 field-enrichment survey (backlog only).** With the round-1
  single-column backlog fully built, surveyed for what the saturated schema still can't answer
  and appended a **Round 2** section to [`TODO.md`](TODO.md): **4 quick-win columns**
  (`employees.hire_source` / `.prior_experience_years`, `time_entries.entry_source`,
  `projects.contract_signed_date`), **3 high-leverage columns** (`project_members.billed_hours`
  — makes project revenue computable; `projects.engagement_manager_id` — partner book-of-
  business; `assignments.assigned_at` — scheduling lead-time, scenario-bearing), and **5
  candidate new tables** (`clients` dim, `time_off` leave spells, `expenses`,
  `performance_reviews`, `employee_skills` bridge). Promoted three prior *Out of scope →
  propose* items (`clients` / `time_off` / `employee_skills`) into in-scope candidate tables now
  that the command supports new tables within a collection, and curated the Out-of-scope bullets
  accordingly. Nothing implemented — the realism-class items route to
  `/data-collection:review-edit-regen-for-realism`, the scenario-bearing ones to
  `/scenario:draft-or-propose labor`.
