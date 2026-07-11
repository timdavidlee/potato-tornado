# Labor round-2 enrichment — task list

- **Created:** 2026-07-11 12:18
- **Scope:** the `labor` collection only.
- **Source:** the *Round 2 survey (2026-07-11)* section of
  [`collections/labor/TODO.md`](../../src/potato_tornado/collections/labor/TODO.md) — the
  authoritative backlog. This file is a working checklist extracted from it; keep the two in
  step (check an item here → check it there when it lands, and record the run in
  [`realism-log.md`](../../src/potato_tornado/collections/labor/realism-log.md)).
- **Status:** nothing implemented yet — labor's round-1 backlog (20 columns) is fully built;
  everything below is new.

## How to work this list

Each task is classed **realism** or **scenario-bearing**:

- **Realism** items → realize with `/data-collection:review-edit-regen-for-realism labor`
  (build the column/table flat, reconcile `realism-guidance.md`, pin an invariant test).
- **Scenario-bearing** items → the *flat* version is realism work; the *surprising subset
  signal* goes through `/scenario:draft-or-propose labor` then
  `/scenario:review-and-edit-regenerate`. Don't plant the signal during the realism pass.

**Definition of done** (every task): draw only from `ctx.dist` / `ctx.rng.child` /
`ctx.entities` on a **name-keyed child stream** without reordering existing draws; reconcile
the matching line in `realism-guidance.md`; add/extend an invariant test in
`tests/collections/labor/test_labor.py`; and the full gate is green
(`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`).

---

## Quick-win columns (realism enrichment)

- [ ] **`employees.hire_source`** (`Utf8`, `{referral, agency, campus, direct, rehire}`)
  - File: `tables/employees.py`. Draw: `ctx.dist.choice` weighted (~0.28 / 0.22 / 0.20 / 0.25 /
    0.05) on a `ctx.rng.child("hire_source")` stream drawn after the existing employee draws.
  - Unlocks: recruiting-channel mix; a slice for attrition / quality-of-hire.
  - Class: **realism** (flat). Scenario variant: *referrals stay longer / churn less*.

- [ ] **`employees.prior_experience_years`** (`Int64`)
  - File: `tables/employees.py`. Draw: `ctx.dist.poisson(~6)` (or `clamped_normal`) nudged by an
    offset keyed to `role` rung; own child stream.
  - Unlocks: experience-vs-pay / experience-vs-role — an external seniority axis distinct from
    the internal `role` ladder.
  - Class: **realism** (flat).

- [ ] **`time_entries.entry_source`** (`Utf8`, `{badge, mobile, web, manual}`)
  - File: `tables/time_entries.py`. Draw: `ctx.dist.choice` weighted on the existing `timesheet`
    child stream (or a new `entry_source` child); **null on no-show rows** (mirror the
    null-clock / `approval_status` rule).
  - Unlocks: timekeeping-system mix.
  - Class: **realism** (flat). Scenario variant: *manual entries rejected / corrected more*
    (echoes the timesheet-compliance signal).

- [ ] **`projects.contract_signed_date`** (`Date`, `≤ start_date`)
  - File: `tables/projects.py`. Draw: `start_date` minus a right-skewed lead
    (`ctx.dist.lognormal` days back) on a `ctx.rng.child("signed")` stream; clamp so it never
    crosses the window start.
  - Unlocks: sales-cycle length (`start_date − contract_signed_date`); booking-vs-start backlog.
  - Class: **realism** (flat).

## High-leverage columns

- [ ] **`project_members.billed_hours`** (`Float64`)
  - File: `tables/project_members.py`. Draw: `allocation_pct/100 × weekly_capacity ×
    weeks(rolled_on → rolled_off) × realization` on a `ctx.rng.child("billed_hours")` stream;
    `null` for non-billable members (mirror the null `bill_rate` rule). Stays a staffing-side
    figure — **not** reconciled against `time_entries` (decoupling is intentional).
  - Unlocks: realized project revenue + gross margin (`billed_hours × (bill_rate − hourly_rate)`)
    per project / practice / client — closes the "revenue approximable but not reconciled" gap.
  - Class: **realism** (flat). Scenario variant: *fixed-fee projects bill fewer hours than
    budgeted (write-offs)* while T&M bill to plan.

- [ ] **`projects.engagement_manager_id`** (`Utf8` FK → `employees.employee_id`)
  - File: `tables/projects.py`. Draw: pick a senior employee (Supervisor / Manager rung) whose
    tenure covers `start_date`, on a `ctx.rng.child("engagement_mgr")` stream (`depends_on`
    already includes `employees`). Distinct from the on-project `role_on_project = 'lead'`.
  - Unlocks: book-of-business by partner (revenue / CSAT / project count); partner
    span-of-control — the accountable-owner dimension `manager_id` doesn't capture for delivery.
  - Class: **realism** (flat). Scenario variant: *a few partners carry an outsized book / higher
    CSAT / more overruns*.

- [ ] **`assignments.assigned_at`** (`Datetime`) — **scenario-bearing**
  - File: `tables/assignments.py`. Draw: `shift.planned_start` minus a right-skewed lead offset
    (`ctx.dist.lognormal`, median ~7 days, tail to same-day) on a `ctx.rng.child("assigned_at")`
    stream, floored at the employee's `hire_date`.
  - Unlocks: scheduling lead-time / short-notice-staffing analysis.
  - Class: **scenario-bearing** → *short-notice shifts (small lead) no-show more* — a staffing
    echo of the clinic lead-time signal and the night-shift no-show gradient. Keep the lead-time
    draw independent of `no_show` for the flat realism pass; plant the correlation only as a
    scenario.

## Candidate new tables (within the collection)

Each needs a new `tables/<table>.py` builder + a `TableSpec` (with `depends_on`) in
`__init__.py`. No `core/registry.py` change (same package).

- [ ] **`clients`** — client dimension behind the bare `projects.client_name`
  - Grain: one row per client. Joins: `projects` gains `client_id`
    (`depends_on=("clients", …)`, FK `projects.client_id → clients`); `client_name` becomes the
    dim's `name`.
  - Key columns: `client_id` (`Utf8`), `name` (`ctx.entities.companies`), `tier` (`Utf8`
    `{strategic, growth, mid, small}`, weighted), `industry` (move off `projects` or keep both),
    `relationship_start_date` (`Date`), `hq_city` (`ctx.entities.cities`, or `LOCATIONS` for a
    clean join).
  - Unlocks: client-concentration (top-N share of staffed hours / revenue), revenue-by-tier,
    multi-project clients, client tenure.
  - Class: **realism**. Scenario variant: *revenue Pareto — a few `strategic` clients carry a
    large share of billed hours*.

- [ ] **`time_off`** — per-employee leave spells  ⚠ removes a deliberate simplification
  - Grain: one row per leave spell. Joins: `depends_on=("employees",)`, FK
    `time_off.employee_id → employees`.
  - Key columns: `leave_type` (`Utf8` `{vacation, sick, holiday, unpaid, parental}`, weighted),
    `start_date` / `end_date` (`Date`, inside `[hire_date, termination_date | end]`, `end ≥
    start`), `hours` (`Int64`). A few spells per employee-year via `ctx.dist.poisson`; own child
    stream.
  - Unlocks: a truer utilization denominator (available = `weekly_capacity_hours` − leave),
    absence analysis, PTO-by-practice / tenure.
  - Class: **realism**. Scenario variant: *sick-leave clusters seasonally or in a practice*.
  - ⚠ **Tension:** the realism-guidance "no PTO / holiday / leave-of-absence spell" simplification
    is currently intentional. Realizing this table means **deleting that bullet** and reconciling
    the utilization guidance in the same change.

- [ ] **`expenses`** — project expense lines
  - Grain: one row per project expense. Joins: `depends_on=("projects", "project_members")`, FK
    `expenses.project_id → projects` (+ optional `expenses.employee_id → employees`).
  - Key columns: `category` (`Utf8` `{travel, lodging, meals, subcontractor, software}`,
    weighted), `amount` (`ctx.dist.money`, category-scaled median), `billable` (`Boolean`,
    pass-through vs absorbed), `incurred_date` (`Date`, inside `[start_date, target_end_date]`).
  - Unlocks: project cost beyond labor (today `budget_amount` prices labor only), T&E by
    practice / client, billable-expense recovery.
  - Class: **realism**. Scenario variant: *travel-heavy spend on off-site / satellite-staffed
    projects* (echoes `off-site-staffing-by-location`).

- [ ] **`performance_reviews`** — periodic review events
  - Grain: one row per employee per review cycle. Joins: `depends_on=("employees",)`, FK
    `performance_reviews.employee_id → employees` and `reviewer_id → employees` (the
    `manager_id`).
  - Key columns: `cycle` (`Utf8`, e.g. `2024-H2`), `rating` (`Int8` 1–5, skewed to 3–4 with a
    mild curve), `promoted` (`Boolean`), on a `ctx.rng.child("reviews")` stream. Emit a row only
    for cycles after `hire_date` and before `termination_date`.
  - Unlocks: performance-over-time, rating distribution, rating → attrition / promotion / pay.
  - Class: **realism**. Scenario variant: *low ratings precede termination, or ratings ladder by
    practice*. (A single `employees.performance_rating` column is the lighter stand-in.)

- [ ] **`employee_skills`** — many-to-many skills bridge behind `employees.primary_skill`
  - Grain: one row per (employee, skill). Joins: `depends_on=("employees",)`, FK
    `employee_skills.employee_id → employees`.
  - Key columns: `skill` (`Utf8`, from the employee's practice `SKILLS_BY_DEPARTMENT` set plus
    the occasional cross-practice skill), `proficiency` (`Utf8` `{beginner, intermediate,
    expert}`), `certified` (`Boolean`). 1–4 skills per employee via `ctx.dist.integers` /
    `poisson`; own child stream; include the employee's `primary_skill` so the bridge stays
    consistent with it.
  - Unlocks: multi-skill staffing, skill-coverage / depth, certification compliance.
  - Class: **realism** (not scenario-bearing on its own).

---

## Suggested order

1. **Quick-win columns** (4) — smallest, all realism; one realism pass can land them together.
2. **`project_members.billed_hours`** — highest-leverage single column (makes revenue
   computable); realism.
3. **`clients` dim** — biggest analytics unlock among the tables; wire `projects.client_id`.
4. Remaining columns (`engagement_manager_id`, then `assigned_at` as a scenario) and tables
   (`expenses`, `performance_reviews`, `employee_skills`) as capacity allows.

Route the scenario-bearing surprises (listed per item) to `/scenario:draft-or-propose labor`
once their flat columns exist — don't plant signals during the realism passes.
