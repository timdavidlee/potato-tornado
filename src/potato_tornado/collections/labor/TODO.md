# labor — field-enrichment TODO

Candidate columns to add to the existing `labor` tables for analytics richness, framed for a
**consulting / project workforce-allocation** analysis (utilization, realization, margin,
bench, project economics, client concentration). Ordered quick wins first (realism
enrichment), then high-leverage items (each unlocks an analysis domain; scenario-bearing ones
go through `/scenario:draft-or-propose`, not the realism command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

Context: the workforce (`employees`) has a **cost** rate (`hourly_rate`) and practices
(`departments`) have an internal `base_hourly_rate`, but there is **no client-facing bill
rate, no billable/non-billable split, no project economics, and no client dimension** — so the
central consulting metrics (utilization, realization, gross margin, revenue by client) can't be
computed today. The additions below close that gap. `shifts`/`assignments`/`time_entries` model
the *timekeeping* side and `projects`/`project_members` the *staffing* side; they are decoupled
by design (see realism-guidance "Projects are decoupled from shifts/time_entries"), so several
suggestions live on the project/staffing side where allocation analysis naturally sits.

## Status (2026-07-01)

All work so far is **flat realism** — no scenario signals planted; each pass reconciled
`realism-guidance.md` and added invariant tests in `tests/collections/labor/test_labor.py`.
Labor gate is green (ruff / pyright / pytest); generation stays byte-deterministic.

**Done (checked below):**
- **Quick wins:** `projects.client_name`, `.industry`, `.billing_type`, `.priority`,
  `employees.weekly_capacity_hours`, `departments.practice_type`, `employees.primary_skill`,
  `employees.work_mode`. (All quick wins are now done.)
- **Margin / realization chain:** item 1 `employees.standard_bill_rate`,
  item 2 `project_members.bill_rate`.
- **Utilization chain:** item 3 `employees.is_billable`, item 4
  `employees.target_utilization_pct`, item 5 `time_entries.billable`. `is_billable` /
  `time_entries.billable` key off `practice_type` as an *expected* realism mix (documented as
  a distribution, not a scenario).
- **Project-economics batch:** item 6 `projects.budget_hours` / `.budget_amount`,
  item 7 `projects.actual_end_date`, item 8 `projects.client_satisfaction` — budgets decoupled
  from staffing, slip not practice-concentrated, CSAT independent of budget/overrun; the two
  outcome fields are populated iff `status = 'completed'`.

**Still open (flat realism, unstarted):** none — all flat-realism items are done. Item 10
`employees.termination_date` is now done too: the rostering-validity decision below was
resolved in favour of **enforcing validity** (option a) — `assignments` and `project_members`
exclude an employee outside their `[hire_date, termination_date)` tenure, and membership roll
dates are bounded by it (a member who leaves mid-project rolls off on their termination date).

- **Timesheet-compliance batch:** item 9 `time_entries.approval_status` / `submitted_late` —
  flat org-wide rates on their own `timesheet` child stream, both populated iff the entry was
  worked (null on no-show, mirroring the null-clock rule); no compliance-by-slice signal
  planted.
- **Staffing timeline:** item 11 `project_members.rolled_on_date` / `rolled_off_date` — each a
  right-skewed offset (join near kickoff, leave near the end) on their own `roll_dates` child
  stream, bounded to `[start_date, target_end_date]`; `rolled_off_date` populated iff the
  project is `completed` (mirrors `actual_end_date`). Turns `allocation_pct` into a capacity
  timeline, so over-allocation is now *detectable* by date overlap but is not planted — the
  concurrency simplification is reconciled accordingly.
- **Org hierarchy:** item 12 `employees.manager_id` — self-referential FK on a `manager` child
  stream; a uniform pick among strictly-more-senior same-department colleagues, null for the
  top of each department (~8–9%). Flat realism (no span-of-control signal); reporting never
  crosses departments and is independent of project staffing.

**Carry caveats before doing:** none outstanding. (`project_members.bill_rate` is now null for
non-billable members — resolved once `is_billable` landed.)

**Scenario signals set up but deliberately not planted** (route to
`/scenario:draft-or-propose labor`): fixed-fee/ industry realization dip (item 2), non-billable
concentration as a *taught* surprise (item 3), billable-share dip by slice (item 5), fixed-fee
budget overruns (item 6), Software Engineering schedule slip (item 7), CSAT dip for
overrun/thin-staffed projects (item 8), margin-by-practice markup compression (item 1),
over-allocation concentrated in a slice (members double-booked past 100% via overlapping
roll-on/off windows, item 11), and attrition concentrated in a slice (a high-turnover practice
or juniors churning faster, item 10).

## Quick wins (realism enrichment)

- [x] **`projects.client_name`** (`Utf8`) — `ctx.entities.companies(n)` (name-keyed off the
  `projects` rng, like other entity draws). Unlocks: revenue / utilization / margin sliced by
  client, and client-concentration analysis (top-N clients as a share of staffed hours).
- [x] **`projects.industry`** (`Utf8`) — `ctx.dist.choice` over a new `INDUSTRIES` catalog
  literal in `constants.py` (Financial Services, Healthcare, Public Sector, Retail,
  Technology, Manufacturing, Energy), weighted. Unlocks: project mix and margin by client
  vertical; a join-free dimension on `projects`.
- [x] **`projects.billing_type`** (`Utf8`, `{time_and_materials, fixed_fee, retainer}`) —
  `ctx.dist.choice` weighted (~0.55 / 0.30 / 0.15). Unlocks: revenue-model split; the basis
  for fixed-fee-margin and realization analysis below. (Plain mix here is realism; the
  *fixed-fee overruns* angle is the scenario — see high-leverage item 6.)
- [x] **`projects.priority`** (`Utf8`, `{low, medium, high}`) — `ctx.dist.choice`
  (~0.3 / 0.5 / 0.2). Unlocks: slicing staffing/attention by engagement priority.
- [x] **`employees.weekly_capacity_hours`** (`Int64`) — keyed off `employment_type` via a
  lookup (`full_time` 40, `part_time` 20, `contractor` 40), with no jitter. Unlocks: an
  honest utilization *denominator* (billable ÷ available) instead of assuming everyone is
  full-time — part-timers otherwise inflate apparent under-utilization.
- [x] **`departments.practice_type`** (`Utf8`, `{delivery, enabling}`) — a fixed lookup on the
  department name (delivery: Strategy & Advisory, Cybersecurity, Data & Analytics, Cloud &
  Infrastructure, Software Engineering, Product & Design; enabling: Project Management, IT
  Support Services), no RNG. Unlocks: a join-free split of client-delivery practices vs.
  internal/overhead practices — the natural grouping for billable-vs-overhead cost and the
  denominator population for `is_billable` (item 3). Realism enrichment.
- [x] **`employees.primary_skill`** (`Utf8`) — `numpy.choice` over a new `SKILLS_BY_DEPARTMENT`
  catalog in `constants.py` keyed on the employee's `department_id` (e.g. Cloud → {AWS, Azure,
  Kubernetes, Terraform}; Data → {SQL, Python, dbt, ML}), on a `ctx.rng.child("skill")` stream
  drawn after existing employee draws. Unlocks: staffing/skills-supply analysis and skill-mix
  by practice. Realism enrichment (a slice dimension; no surprising segment behaviour).
- [x] **`employees.work_mode`** (`Utf8`, `{onsite, hybrid, remote}`) — weighted `numpy.choice`
  (0.30 / 0.50 / 0.20), on a `ctx.rng.child("work_mode")` stream drawn after existing employee
  draws. Unlocks: workforce work-arrangement mix, a slice for real-estate / return-to-office
  analysis. Realism enrichment — kept **flat** here; the scenario-bearing variant (remote
  concentrating in a satellite office or one practice) is deliberately *not* planted → route to
  `/scenario:draft-or-propose`. Distinct from the project-level off-site signal
  (member-vs-project location), which already exists — this is the employee's own arrangement.

## High-leverage additions

### 1. `employees.standard_bill_rate` — done (flat)
- [x] Client-facing list rate = `hourly_rate` (cost) × a role-indexed markup × small jitter
  (`Float64`, rounded to cents). Draw sketch: markup ladder ~2.6× Associate → ~3.0× Manager
  from a lookup on `role`, times `ctx.dist.clamped_normal` jitter on a `ctx.rng.child("bill_rate")`
  stream (drawn after existing employee draws so it doesn't shift them).
- **Unlocks:** gross margin (`standard_bill_rate − hourly_rate`) per employee and, rolled up,
  per practice; the denominator for realization (item 2).
- **Class:** realism enrichment (a derived rate). **Scenario-bearing variant:** if the markup
  *compresses at senior rungs* or *differs by practice* (e.g. Strategy & Advisory carries a
  fatter markup than IT Support Services), the "which practice actually earns the margin"
  surprise → route to `/scenario:draft-or-propose` with that signal named. Keep the base draw
  flat for realism; plant the compression only as a scenario.

### 2. `project_members.bill_rate` — done (flat; null for non-billable members)
- [x] The negotiated rate this member is billed to the client at *on this project* = the
  employee's `standard_bill_rate` × a realization factor < 1 (a discount), nullable when the
  member is non-billable (`Float64`). Draw sketch: join `standard_bill_rate` from `employees`
  (declare `depends_on` already covers `employees`), multiply by `ctx.dist.clamped_normal`
  discount (~0.85, clamped [0.6, 1.0]) on a `project_members` child stream.
- **Unlocks:** realization % (`bill_rate ÷ standard_bill_rate`), rate leakage, and project
  revenue ≈ `Σ bill_rate × allocated hours`; combined with cost rate, project-level margin.
- **Class:** **scenario-bearing** → the discount is not uniform: e.g. **fixed-fee** projects
  (item on `projects.billing_type`) or a **specific industry/client tier** realize a
  materially lower rate than time-and-materials work. Route to `/scenario:draft-or-propose`;
  name the subset (billing_type or industry) that carries the depressed realization.

### 3. `employees.is_billable` — done (flat, keyed to practice_type)
- [x] Whether the employee is a client-billable consultant vs. overhead/bench (`Boolean`).
  Draw sketch: `ctx.dist.bernoulli` with a per-department probability lookup (delivery
  practices ~0.9 billable; support/PM practices lower), on a `ctx.rng.child` stream drawn
  after existing employee draws.
- **Unlocks:** the utilization *numerator population* (who is expected to be billable), bench
  headcount, and billable-vs-overhead cost ratios per practice.
- **Class:** **scenario-bearing** → non-billable staff concentrate in the overhead practices
  (**IT Support Services**, **Project Management**) while delivery practices are ~all billable.
  Route to `/scenario:draft-or-propose` with the practice-concentration signal named. (A flat
  org-wide billable rate would be realism; the *concentration in support practices* is the
  teachable subset.)

### 4. `employees.target_utilization_pct` — done (Int64, null for non-billable)
- [x] The utilization target the employee is held to (`Float64` or `Int64`, e.g. 60–85).
  Draw sketch: a lookup keyed on `role` (juniors carry higher targets, e.g. Associate ~80 →
  Manager ~55) with small `ctx.dist.clamped_normal` jitter, only meaningful where
  `is_billable` (null/NA for non-billable). Depends on item 3.
- **Unlocks:** actual-vs-target utilization gaps, over/under-utilization by seniority.
- **Class:** realism enrichment (a per-role target ladder). Becomes scenario-bearing only if
  paired with an *actual* utilization that systematically misses target for a slice — that
  belongs to a scenario, not here.

### 5. `time_entries.billable` — done (flat, keyed to shift dept practice_type)
- [x] Whether the worked shift was billable client time vs. internal/bench time (`Boolean`;
  `False`/NA on no-show rows to respect the null-clock invariant). Draw sketch:
  `ctx.dist.bernoulli` with a probability that can key off `shifts.department_id` /
  `shift_window`, on a `ctx.rng.child("billable")` stream (drawn alongside the existing
  `attendance`/`overtime` child streams, so existing draws don't shift).
- **Unlocks:** *actual* utilization from the timekeeping side (billable hours ÷ worked hours),
  independent of the staffing-side allocation — the single most important consulting KPI.
- **Class:** **scenario-bearing** → billable share dips for a slice (e.g. an overhead practice
  runs mostly non-billable internal time, or bench time clusters in a shift window). Route to
  `/scenario:draft-or-propose` and name the low-billable subset. Keep it a flat rate if you
  only want the realism dimension.

### 6. `projects.budget_hours` and `projects.budget_amount` — done (flat)
- [x] Contracted delivery budget: `budget_hours` (`Int64`) scaled by team size × duration, and
  `budget_amount` (`Float64`) ≈ `budget_hours` × a blended bill rate. Draw sketch:
  `ctx.dist.integers`/`lognormal` on a `projects` child stream, sized off `duration_days` (and
  optionally an assumed team size), rounded.
- **Unlocks:** budget-vs-burn / project economics; with `bill_rate` and worked hours, whether a
  project is on track to margin.
- **Class:** realism enrichment for the raw budget columns. **Scenario-bearing variant:**
  **fixed-fee** projects (or a given practice) systematically **overrun** budget while
  time-and-materials do not → route to `/scenario:draft-or-propose` with the overrun-by-
  billing_type signal named (this is the natural partner to item 2's realization signal).

### 7. `projects.actual_end_date` — done (flat; slip not practice-concentrated)
- [x] The date the project actually ended, nullable while `status = 'active'` / `'on_hold'`
  (`Date`). Draw sketch: for `completed` projects, `target_end_date` + a signed slip drawn from
  `ctx.dist` (mostly small, right-skewed late tail) on a `projects` child stream; null
  otherwise.
- **Unlocks:** schedule slippage / delivery-overrun analysis (actual vs target end), cycle-time
  by practice.
- **Class:** **scenario-bearing** → overruns concentrate in one practice (a natural echo of the
  **Software Engineering owns the overtime tail** scenario — release crunches slip end dates).
  Route to `/scenario:draft-or-propose`; name the practice that slips. Keep the null-while-open
  rule as an invariant in `realism-guidance.md`.

### 8. `projects.client_satisfaction` — done (flat)
- [x] Client CSAT score for the engagement (`Int8` on a 1–5 scale, or `Float64`), **nullable
  while `status != 'completed'`** (no score until the project closes). Draw sketch: for
  completed projects, `ctx.dist.clamped_normal(mean≈4.1, sd≈0.7, 1, 5)` rounded (or
  `ctx.dist.integers(1, 5)` weighted high), on a `ctx.rng.child("csat")` stream; null otherwise.
- **Unlocks:** delivery-quality analysis — CSAT by practice, client, billing_type, or team
  seniority; the outcome variable that budget/realization/overrun columns predict.
- **Class:** **scenario-bearing** → satisfaction dips for a subset (fixed-fee overruns, or
  projects that slipped their `actual_end_date` from item 7, or thin-staffed teams). Route to
  `/scenario:draft-or-propose` and name the low-CSAT slice; keep the base draw flat if you only
  want the realism dimension. (Depends on nothing, but pairs naturally with items 6–7.)

### 9. `time_entries.approval_status` / `submitted_late` — done (flat)
- [x] Timesheet-compliance fields on worked entries: `approval_status` (`Utf8`,
  `{approved, pending, rejected}`, 0.90 / 0.07 / 0.03) and `submitted_late` (`Boolean`,
  ~0.12) — both **null** on no-show rows (there is no timesheet to submit or approve), so each
  is populated iff `no_show = false` (mirrors the null-clock rule; cleaner than a `False`
  sentinel). Drawn on a `ctx.rng.child("timesheet")` stream sized `n = joined.height`, after
  the existing `attendance`/`overtime`/`billable` child streams so those draws don't shift.
- **Unlocks:** timesheet-hygiene / revenue-leakage analysis — unapproved or late-submitted
  hours can't be billed; compliance rates by practice or shift window.
- **Class:** realism enrichment for the flat rates; **scenario-bearing** if late/rejected
  timesheets concentrate in a practice or the night window (an ops-discipline echo of the
  no-show-by-window signal). Route the concentration to `/scenario:draft-or-propose`.

### 10. `employees.termination_date` — done (flat; rostering-validity enforced)
- [x] The date an employee left the firm, **null for active staff** (`Date`). An ~18% attrition
  flag on a `ctx.rng.child("attrition")` stream, then a tenure offset ≥90 days after
  `hire_date`, kept strictly before `end_date`; null otherwise.
- **Unlocks:** attrition / retention analysis — turnover rate by practice, role, tenure, and
  location; headcount-over-time.
- **Class:** realism enrichment (flat attrition). **Scenario-bearing variant:** attrition
  concentrates in a slice (a high-turnover practice, or juniors churning faster) → route to
  `/scenario:draft-or-propose` with the segment named. Not planted here.
- **✔ Resolved the ⚠ decision by enforcing validity (option a).** `assignments` rosters an
  employee onto a shift only within `[hire_date, termination_date)`, and `project_members`
  staffs only employees whose tenure overlaps the project window, with roll-on ≥ `hire_date`
  and a mid-project leaver rolling off on their `termination_date` (so `rolled_off_date` can be
  non-null even on an open project). The rubric's "No terminations or leave" simplification and
  the roll-date invariants were reconciled in the same change; PTO/other leave stays unmodelled.

## Later / depends-on

### 11. `project_members.rolled_on_date` / `rolled_off_date` — done (flat)
- [x] When the member joined and left the project, within `[projects.start_date,
  target_end_date]` (`Date`; `rolled_off` nullable while active). Draw sketch: per-membership
  offsets via `ctx.dist` on a `project_members` child stream, ordered so `rolled_off >
  rolled_on`. Depends on nothing new but pairs with item 6.
- **Unlocks:** allocation-over-time and concurrency modelling — turns `allocation_pct` from a
  static number into a capacity timeline, and directly addresses the realism-guidance
  simplification that "concurrency is not modelled" (summed allocation can exceed 100%). With
  dates, real over-allocation becomes detectable.
- **Class:** realism enrichment (adds the missing time axis to staffing). A genuine
  over-allocation *signal* (members double-booked past 100% in a slice) would then be
  scenario-bearing on top of it.

### 12. `employees.manager_id` — done (flat)
- [x] Self-referential FK to a more-senior employee in the same department (`Utf8`, nullable
  for the top of each practice). Draw sketch: within each department, pick a manager for each
  employee from the higher-`role`-rung members via `ctx.rng.child("manager")`; leave the most
  senior without one. (~8–9% managerless — the top rung of each department.)
- **Unlocks:** org hierarchy / span-of-control analysis, and "who staffs whom" roll-ups.
- **Class:** realism enrichment (an org-tree dimension). Not scenario-bearing on its own.

## Out of scope (not field enrichment)

- **A `clients` table** (client_id, industry, tier, contract start) with `projects.client_id`
  as an FK is a *new entity*, not a column — if the client dimension needs its own attributes
  beyond a name string on `projects`, that's `/data-collection:propose`, not this doc. The
  quick-win `projects.client_name` / `projects.industry` columns are the in-scope stand-in.
- **A per-project timesheet** linking `time_entries` to `projects` (e.g.
  `time_entries.project_id`) is effectively a new bridge between the decoupled timekeeping and
  staffing halves; wiring shifts/assignments to projects is a modeling change (new depends_on
  and a shift→project mapping that doesn't exist today), closer to a new table than a field.
  Note it, but treat it as `/data-collection:propose` territory rather than realizing it here.
- **A `skills` bridge** (employee-skill many-to-many, or a `skills` catalog table with FKs) is a
  *new entity*. The single-valued `employees.primary_skill` column above is the in-scope
  stand-in; a full multi-skill matrix is `/data-collection:propose` territory.
- **A `time_off` / PTO table** (per-employee leave spells) is a new entity, not a column — it
  would give a truer utilization denominator than `weekly_capacity_hours` alone, but belongs to
  `/data-collection:propose`. (`employees.termination_date`, item 10, is the in-scope
  single-column stand-in for the coarsest availability gap.)
- No new `core/distributions.py` helper is required — every draw above composes from existing
  `ctx.dist` (`choice` / `bernoulli` / `integers` / `clamped_normal` / `lognormal` /
  `dates_between`), `ctx.rng.child`, and `ctx.entities.companies`.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items. Most here are also *future-scenario* candidates — route signal-bearing ones
to `/scenario:draft-or-propose`.

- [ ] **Consulting dimensions are flat and mutually independent.** `industry` / `billing_type`
      / `priority` are drawn independently of each other and of `department_id`; an industry ×
      billing_type cross-tab reads uniform. Confirm the flatness is acceptable or plant a
      correlated mix.
- [ ] **Attendance / overtime independence.** No per-employee reliability or streaks; overtime
      depends on department, not individual. Flag only if per-person autocorrelation is
      expected.
- [ ] **Bill / project economics are flat.** Realization, markup-by-practice, and budget burn
      carry no planted slice signal — any margin-by-practice roll-up reads flat (scenario-bearing
      → `/scenario:draft-or-propose`).
