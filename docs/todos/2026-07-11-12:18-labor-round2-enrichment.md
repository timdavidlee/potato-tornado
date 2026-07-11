# Labor round-2 — dated working checklist (2026-07-11 12:18)

- **Scope:** the `labor` collection only.
- **Source of truth:** the *Round 2 survey (2026-07-11)* + *Candidate new tables* sections of
  [`collections/labor/TODO.md`](../../src/potato_tornado/collections/labor/TODO.md).
  This checklist carries **no item substance of its own** — each item below links to its entry in
  `TODO.md` for the recipe, class (realism vs scenario-bearing), and definition of done. It exists
  only to track this dated run's progress: tick an item here when it lands, tick it in `TODO.md`
  too, and log the run in
  [`realism-log.md`](../../src/potato_tornado/collections/labor/realism-log.md). Workflow lives in
  [collections/CLAUDE.md](../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands.
- **Status:** round-1 (20 columns) already built. The full round-2 batch — 6 columns + 5 new
  tables — landed 2026-07-11; only the `assignments.assigned_at` short-notice signal routes to a
  scenario.

## Checklist

**Round-2 quick-win columns →** [`TODO.md` § Round 2 survey](../../src/potato_tornado/collections/labor/TODO.md#round-2-survey-2026-07-11)

- [x] `employees.hire_source` *(2026-07-11)*
- [x] `employees.prior_experience_years` *(2026-07-11)*
- [x] `time_entries.entry_source` *(2026-07-11)*
- [x] `projects.contract_signed_date` *(2026-07-11)*

**Round-2 high-leverage columns →** [`TODO.md` § Round 2 survey](../../src/potato_tornado/collections/labor/TODO.md#round-2-survey-2026-07-11)

- [x] `project_members.billed_hours` *(2026-07-11)*
- [x] `projects.engagement_manager_id` *(2026-07-11)*
- [x] `assignments.assigned_at` *(2026-07-11 — flat; short-notice signal routed)*

**Candidate new tables →** [`TODO.md` § Candidate new tables](../../src/potato_tornado/collections/labor/TODO.md#candidate-new-tables-within-this-collection)

- [x] `clients` (+ `projects.client_id` rewire) *(2026-07-11)*
- [x] `time_off` *(2026-07-11 — retired the "no PTO/leave" simplification)*
- [x] `expenses` *(2026-07-11)*
- [x] `performance_reviews` *(2026-07-11)*
- [x] `employee_skills` *(2026-07-11)*
