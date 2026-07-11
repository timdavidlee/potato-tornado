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
2026-07-11)

## Realism iterations

- **2026-07-01 — Realism audit + invariant tests.** Cross-checked referential integrity, the
  no-show ⇔ null-clocks rule, `worked ≥ planned` overtime, the pay/bill ladders, and the
  off-site-by-location gradient; added invariant tests. (`8ffba28`)
- **2026-07-01 — Realism-pass tuning.** Distribution/weight tuning across the enrichment
  columns (attendance-by-window, overtime concentration, project staffing). (`e27dc41`)
- **2026-07-11 — Right-censoring of project completions (cross-collection convention).** A
  completion past the snapshot is unobservable, so `projects` now right-censors it: after the
  existing `slip` draw, `candidate_end = target_end + slip`; a project *drawn* `completed` whose
  `candidate_end >= config.end_date` is **downgraded to `active`** with null `actual_end_date` /
  `client_satisfaction` (exactly like an originally-active project). Pure re-derivation of
  already-drawn values — no new RNG, no reordering — so `slip`/`csat` stay drawn for all `n` on
  their child streams and every other column stays byte-identical (verified before/after at
  `seed=7,scale=0.3`, `seed=13,scale=0.3` fixture, and `seed=7,scale=1.0`: only `projects`
  {`status`,`actual_end_date`,`client_satisfaction`} and the **required `project_members`
  cascade** changed). The cascade is correct-by-design: `project_members` reads
  `projects.status`, so a flipped project's non-terminated members get `rolled_off_date → null`
  and `billed_hours` recomputed (billing through `target_end_date`), while terminated members
  keep their termination roll-off — the roll-off invariant test still holds. Observed completed
  share drops from the 0.40 draw to ~0.31 (~20–25% of drawn-completed present as active).
  Reconciled `realism-guidance.md` (split the "Project dates ordered" invariant, added the
  "Actual end is right-censored" invariant, updated "Project teams" draw-vs-observed, "Schedule
  slip" right-truncation, and a cross-collection note: `streaming` mirrors this on subscriptions,
  `hotel` deliberately retains the checkout-spill convention as a documented exception). Pinned
  `test_completed_projects_end_within_window`. Not in the `TODO.md` open-items list — recorded
  here as its own realism iteration.

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
- **2026-07-11 — Round-2 quick-win columns (4, flat realism).** Built the four round-2
  quick-win columns, each on its own name-keyed child stream so no existing draw shifted
  (verified column-for-column at `seed=7, scale=0.3`): `employees.hire_source`
  (`HIRE_SOURCES` mix, `child("hire_source")`), `employees.prior_experience_years`
  (Poisson(4) + 2×role-rung offset, `child("experience")`, drawn independently of pay),
  `time_entries.entry_source` (badge/mobile/web/manual, `child("entry_source")`, null on
  no-show mirroring the approval fields), and `projects.contract_signed_date`
  (lognormal median ≈60d lead before start, `child("signed")`, floored at the window start).
  Reconciled `realism-guidance.md` (invariants + mixes) and added invariant tests in
  `tests/collections/labor/test_labor.py`.
- **2026-07-11 — Round-2 R2-1 `project_members.billed_hours` (high-leverage, flat).** A
  staffing-side hours estimate `= allocation_pct/100 × weekly_capacity × weeks-on-project ×
  realization`, realization ~Normal(0.85, 0.1) clamped [0.4, 1.0] on `child("billed_hours")`;
  open memberships bill through `target_end_date`; null for non-billable members (mirrors
  `bill_rate`). Makes project revenue computable staffing-side (`Σ billed_hours × bill_rate`)
  while staying decoupled from `time_entries`. Reconciled the "revenue approximable but not
  reconciled" note, added invariant + distribution lines, pinned an invariant test. No existing
  column shifted.
- **2026-07-11 — Round-2 R2-2 `projects.engagement_manager_id` (high-leverage, flat).** FK to a
  senior employee (Supervisor/Manager rung) whose tenure covers the project `start_date`, on
  `child("engagement_mgr")`, with a fallback chain (widen to Lead+, then any employed employee)
  for dates the senior pool doesn't cover. Added `"employees"` to `projects.depends_on` in
  `__init__.py` — build order is unchanged (employees already builds before projects), so
  `client_name` (Faker) did not shift; verified column-for-column. The accountable-owner
  dimension, flat (no partner-book-concentration signal). Reconciled the referential invariant +
  a deliberate-simplification note, pinned an FK test.
- **2026-07-11 — Round-2 R2-3 `assignments.assigned_at` (flat scenario-column).** The roster
  publish time = shift `planned_start` minus a right-skewed lead (lognormal, median ≈7d) on
  `child("assigned_at")`, floored at the employee's hire date. Built FLAT only — independent of
  `no_show` (the short-notice→no-show correlation is a deferred scenario, not planted). Added a
  scheduling-lead-time distribution line + an ordering invariant test. No existing column
  shifted (`assigned_role`'s root-stream draw unchanged).
- **2026-07-11 — Round-2 new table `employee_skills` (bridge, flat).** One row per
  (employee, skill): 1–4 distinct skills per employee sampled without replacement from the
  employee's practice `SKILLS_BY_DEPARTMENT` set and always including `primary_skill`
  (`child("skills")`), plus `proficiency` (`child("proficiency")`) and `certified`
  (`child("certified")`). `depends_on=("employees","departments")`. Added invariants (skill ∈
  practice set, includes primary, 1–4/employee) + mixes and an FK test. New table is name-keyed
  and consumes no Faker, so no existing table shifted.
- **2026-07-11 — Round-2 new table `performance_reviews` (event, flat).** One row per (employee,
  half-year cycle) for cycles inside the employee's employment window (`2022-H1`..`2024-H2` on
  the default window, derived from the config, not hard-coded); `rating` = Normal(3.6, 0.9)
  clamped/rounded to 1–5, `promoted` ~Bernoulli(0.10), `reviewer_id = manager_id` (nullable), on
  `child("reviews")`. `depends_on=("employees",)`. Independent of attrition (no
  low-rating→termination signal). Added invariants (in-window, reviewer=manager, rating scale) +
  a rating-skew mix and a rating-range test. No existing table shifted.
- **2026-07-11 — Round-2 new table `expenses` (event, flat).** ~Poisson(4) lines per project on
  the table's own root stream; `category` (travel/lodging/meals/subcontractor/software) with a
  common lognormal `amount` (median ~$500) category-scaled; `billable` ~0.70; `incurred_date`
  uniform in `[start, target_end]`; `employee_id` null ~25% else a staffed member of that
  project. `depends_on=("projects","project_members")`. Decoupled from `budget_amount` /
  `billed_hours`. Added invariants (project FK, amount>0, in-window, employee ∈ project members)
  + an expense mix + a decoupled-cost-view simplification, and a project-FK test. No existing
  table shifted.
- **2026-07-11 — Round-2 new table `time_off` (event; retires a simplification).** Per-employee
  leave spells: ~Poisson(4 × tenure-years) spells on `child("time_off")`, `leave_type`
  weighted (vacation/sick/holiday/unpaid/parental), start uniform in the employment window and
  per-type right-skewed durations, all bounded to `[hire_date, min(termination_date, end_date))`
  with `end ≥ start`; `hours` ≈ working-days × 8. `depends_on=("employees",)`. **Retired** the
  "no PTO / holiday / leave-of-absence spell" deliberate simplification (rewrote that bullet to
  note `time_off` now supplies a truer utilization denominator while staying decoupled from
  shifts). Added invariants + a leave mix and a within-window test. No existing table shifted.
- **2026-07-11 — Round-2 new table `clients` + `projects` rewire (dimension).** New `clients`
  dimension (`name` via Faker companies, `tier`/`industry`/`hq_city`/`relationship_start_date`,
  ~20 at scale 1). `projects` gains a `client_id` FK sampled uniformly on `child("client")` and
  its `client_name` is now `clients.name` denormalized by the join (replacing the bare per-
  project Faker company). Placed the `clients` TableSpec **after** `employees` in the tuple so
  `employees`' Faker draws stay first — `employees.full_name`/`email` unchanged; the only
  intended shift is `projects.client_name` (now the denormalized client name). **Rewrote** the
  "No client master" deliberate simplification (client master now exists; assignment is still
  uniform, no revenue-Pareto planted) and updated the project-catalog invariant + mixes. Added a
  `projects.client_id ∈ clients` FK test; `industry` kept on both tables so
  `test_project_dimensions_are_from_the_catalog` is unaffected.
