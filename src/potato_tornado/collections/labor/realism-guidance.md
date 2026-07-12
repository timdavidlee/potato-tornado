# Realism guidance — labor

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Rostering stays within a department.** Every `assignments` row pairs an employee with a
  shift in that employee's home department (`assignments.py` groups employees by
  `department_id` before picking).
- **Rostered only while employed.** An `assignments` row places an employee on a shift only
  within their employment: `hire_date ≤ shift.planned_start::date` and (`termination_date` is
  null or `shift date < termination_date`). Nobody clocks in before they were hired or after
  they left the firm.
- **One clock record per assignment.** `time_entries` is 1:1 with `assignments`
  (`time_entries.height == assignments.height`).
- **No-show ⇔ null clocks.** A `no_show = true` row has null `clock_in` / `clock_out` /
  `worked_hours`; a `no_show = false` row has all three populated. There is no third state.
- **Time ordering.** When present, `clock_out > clock_in`, and
  `worked_hours ≈ planned_hours + overtime` with `overtime ≥ 0` — so a worked shift never
  logs *fewer* hours than planned.
- **Shift arithmetic.** `planned_end = planned_start + planned_hours`; `planned_hours ∈
  {8, 10, 12}`; `required_headcount ∈ [2, 8]`.
- **Pay is positive and ordered.** `hourly_rate > 0`, built as department base × seniority
  multiplier × jitter, so within a department a more senior role trends higher.
- **Bill rate sits above cost.** `employees.standard_bill_rate > hourly_rate` for every
  employee (the markup is ≥ 2.6× before jitter, so even the lowest jittered rate clears cost);
  both are positive.
- **Weekly capacity is a fixed function of employment type.** `weekly_capacity_hours ∈
  {20, 40}` — 20 for `part_time`, 40 for `full_time` / `contractor`. No jitter.
- **Project bill rate is a realized discount, set only for billable members.**
  `project_members.bill_rate` is populated **iff** the member's `employees.is_billable` is true
  — non-billable (bench / overhead) members carry a `null` bill rate (there is no client rate
  for them). When present, it is `> 0` and lies in `[0.6, 1.0] ×` the member's
  `employees.standard_bill_rate` — a member is never billed above their standard list rate.
- **Billed hours are set only for billable members, and never negative.**
  `project_members.billed_hours` is populated **iff** the member's `employees.is_billable` is
  true (non-billable members carry `null`, like `bill_rate`). When present it is `>= 0` — a
  staffing-side estimate `= allocation_pct/100 x weekly_capacity_hours x weeks-on-project x
  realization`, where an open membership (null `rolled_off_date`) bills through the project's
  `target_end_date`.
- **Project catalogs & client FK.** `projects.client_id ∈ clients` (every project points at a
  real client account), and `projects.client_name` is that client's `name` denormalized onto
  the project (so `projects.client_name` always equals the joined `clients.name`) — still an
  entity company name, no longer a bare per-project string. `projects.industry ∈ INDUSTRIES`,
  `projects.billing_type ∈ BILLING_TYPES`, `projects.priority ∈ PROJECT_PRIORITIES` are all
  from their fixed catalogs. On the `clients` dimension: `tier ∈ CLIENT_TIERS`
  (`{strategic, growth, mid, small}`), `industry ∈ INDUSTRIES`, `hq_city ∈ LOCATIONS`.
- **Practice classification.** `departments.practice_type ∈ {delivery, enabling}`, and it is
  `enabling` for exactly the two overhead functions (`ENABLING_DEPARTMENTS` = Project
  Management, IT Support Services) and `delivery` for the other six.
- **Skill matches practice.** `employees.primary_skill` is one of `SKILLS_BY_DEPARTMENT` for
  the employee's own department — a consultant's skill always belongs to their practice.
  `employees.work_mode ∈ {onsite, hybrid, remote}`.
- **Employee catalogs & non-negativity.** `employees.hire_source ∈ HIRE_SOURCES`
  (`{referral, agency, campus, direct, rehire}`), and `employees.prior_experience_years ≥ 0`
  for every employee (a Poisson base plus a non-negative seniority offset).
- **Skills bridge is consistent with the practice and the primary skill.** Every
  `employee_skills` row references a real employee (`employee_id ∈ employees`) and a `skill`
  from that employee's own department's `SKILLS_BY_DEPARTMENT` set. Each employee carries
  **1–4** skills, all distinct, and the set **always includes** the employee's
  `primary_skill`. `proficiency ∈ {beginner, intermediate, expert}`.
- **Reviews sit inside employment, and rate on a 1–5 scale.** Every `performance_reviews` row
  references a real employee (`employee_id ∈ employees`); `reviewer_id` is the employee's
  `manager_id` (so it is null exactly when they have no manager, else resolves to an employee).
  A row exists only for a half-year `cycle` (`YYYY-H1` / `YYYY-H2`) whose review date falls
  **after** `hire_date` and **before** `termination_date` (when set) — no review predates hire
  or lands on/after a leaver's date. `rating ∈ [1, 5]` (integer).
- **Expense lines belong to a project, are positive, and dated inside its run.** Every
  `expenses` row references a real project (`project_id ∈ projects`); `category ∈ {travel,
  lodging, meals, subcontractor, software}`; `amount > 0`; `incurred_date ∈ [start_date,
  target_end_date]`. `employee_id`, when non-null, is one of **that project's** staffed
  `project_members` (never an unrelated employee).
- **Leave spells sit inside employment.** Every `time_off` row references a real employee
  (`employee_id ∈ employees`); `leave_type ∈ {vacation, sick, holiday, unpaid, parental}`;
  `start_date ≥ hire_date`, `end_date ≥ start_date`, and `end_date <
  min(termination_date, end_date)` — a spell never predates hire or lands on/after a leaver's
  date. `hours > 0`.
- **Manager is a senior same-department colleague.** `employees.manager_id`, when present,
  references another employee (never self) in the **same** `department_id` with a **strictly
  higher** `role` rung. It is null **exactly** for whoever sits at the top of their department
  — every Manager, plus the highest-present rung wherever a department has no Manager (~8–9%
  of staff overall).
- **Utilization target tracks billability.** `employees.target_utilization_pct` is populated
  **iff** `is_billable` is true — every billable employee has a target, every non-billable one
  has `null`. No third state.
- **A no-show is never billable.** `time_entries.billable` is `false` on every `no_show = true`
  row (no worked time to bill); it can be true or false on worked rows.
- **Timesheet fields close with the worked entry.** `time_entries.approval_status`,
  `time_entries.submitted_late`, and `time_entries.entry_source` are populated **iff**
  `no_show = false` — all three are `null` on no-show rows (no timesheet to submit, approve, or
  capture). `approval_status ∈ {approved, pending, rejected}`;
  `entry_source ∈ {badge, mobile, web, manual}`.
- **Budgets are positive.** `projects.budget_hours > 0` and `projects.budget_amount > 0`.
- **Outcome fields close with the project.** `projects.actual_end_date` and
  `projects.client_satisfaction` are populated **iff** `status = 'completed'` — both are
  `null` for `active` / `on_hold` projects. `client_satisfaction ∈ [1, 5]`.
- **Hire dates are in-window.** `hire_date ≤ end_date` (and no later); it may fall up to
  ~5 years before `start_date`.
- **Termination is after hire and in-window.** `employees.termination_date`, when present, is
  `> hire_date` (at least ~90 days of tenure) and strictly before the window end (`< end_date`);
  it is `null` for active staff (~82%).
- **Locations are from the catalog.** `employees.location_city` and
  `projects.location_city` are both drawn from the fixed `LOCATIONS` set (6 offices) — never
  free-form cities, so "same location" is a clean join.
- **Project dates ordered.** `projects.target_end_date > start_date` (a 60–300 day run);
  `start_date` is in `[start_date, end_date)`, but `target_end_date` **may fall past the window
  end** (it's a target, not an actual). `projects.contract_signed_date ≤ start_date` (the sale
  closes before delivery starts) and is never before the window start (floored at
  `config.start_date`), so it is always inside `[start_date, project.start_date]`.
- **Actual end is right-censored at the window.** `projects.actual_end_date`, when present, is
  **never `>= end_date`** — a completion past the snapshot is unobservable. A project *drawn*
  `completed` whose candidate completion (`target_end_date + slip`) lands on/after `end_date` is
  **downgraded to `active`** with a `null` `actual_end_date` / `client_satisfaction` (exactly
  like an originally-active project). Contrast `target_end_date`, which is a plan and may spill
  past the window; `actual_end_date` is an observed event and may not. This is the shared
  right-censoring convention (see the cross-collection note under *Deliberate simplifications*).
- **One lead per project.** Each `projects` row has exactly one `project_members` row with
  `role_on_project = 'lead'`; the rest are `contributor`. Every project has ≥1 member. The
  lead is the team's most senior member (highest `role` rung; ties go to the earliest pick).
- **A member appears once per project.** `(project_id, employee_id)` is unique in
  `project_members`; `allocation_pct ∈ {25, 50, 75, 100}`.
- **Membership roll dates sit inside the project *and* employment window.**
  `project_members.rolled_on_date ∈ [max(project.start_date, hire_date), target_end_date)` and
  is never null — a member never rolls on before kickoff or before they were hired.
  `rolled_off_date`, when present, is `> rolled_on_date` and `≤ target_end_date`, and never
  after the member's `termination_date`. `rolled_off_date` is populated **iff** the project's
  `status = 'completed'` **or** the member left the firm on/before the project's target end
  (`termination_date ≤ target_end_date`) — in the latter case it equals `termination_date`, so
  it can be non-null even on an open project. It is null only while the member is still employed
  and the project is still `active` / `on_hold`.
- **Referential integrity.** `assignments.employee_id ∈ employees`,
  `assignments.shift_id ∈ shifts`, `time_entries` FKs resolve;
  `project_members.employee_id ∈ employees`, `project_members.project_id ∈ projects`,
  `projects.department_id ∈ departments`; `employees.manager_id`, when non-null, resolves to
  another `employees` row. `projects.engagement_manager_id ∈ employees` (never null) — the
  accountable owner, always a real employee.

## Distributions & mixes (should look like the real world)

- **Role pyramid.** Associate 0.50 → Senior Associate 0.25 → Lead 0.13 → Supervisor 0.08 →
  Manager 0.04. Most staff are junior.
- **Employment mix.** full_time 0.60 / part_time 0.30 / contractor 0.10.
- **Attrition.** ~18% of employees have a `termination_date` (have left the firm); a leaver's
  date is a tenure offset ≥90 days after hire, uniform up to the window end. Flat — drawn
  independently of practice, role, and tenure (no high-turnover slice is planted; that
  concentration is a future scenario). Staffing respects it: terminated staff drop out of
  rosters and project pools after their date.
- **Pay ladder.** `hourly_rate = department_base × (1 + 0.18 × role_index) × jitter`.
  Department (practice) base $64–95/hr (~48% spread); +18% per seniority rung; ±6% jitter
  clamped to [0.85, 1.2]×. The base spread is wider than one rung, so department can outweigh
  a single step of seniority. See `scenarios/department-base-can-outweigh-a-rung.md`.
- **Bill-rate ladder.** `standard_bill_rate = hourly_rate × markup × jitter`, markup laddering
  by role from ~2.6× (Associate) to ~3.0× (Manager), jitter ±5% clamped to [0.9, 1.1]. Gross
  margin (`standard_bill_rate − hourly_rate`) is therefore always positive and widens up the
  ladder. Markup is flat *by role only* — no per-practice compression (a future scenario).
- **Realization.** For billable members, `project_members.bill_rate = standard_bill_rate ×
  realization`, realization ~Normal(mean, 0.06) clamped to [0.6, 1.0] — overall mean ≈ 0.85,
  i.e. members bill at ~85% of list. The Normal's *mean* is keyed off the project's
  `billing_type` (`time_and_materials` 0.89 / `retainer` 0.85 / `fixed_fee` 0.78), so
  realization is **not** flat across the commercial model — fixed-fee work realizes a ~12pt
  lower rate than T&M (see `scenarios/fixed-fee-engagements-realize-lower.md`); the type means
  blend (weights 0.55 / 0.15 / 0.30) back to the ~0.85 firm-wide mean. Still independent of
  `industry` and client. Non-billable members (~25% of the workforce) carry a null bill_rate.
- **Billed hours.** For billable members, `billed_hours` scales allocation share × weekly
  capacity × weeks-on-project × a realization factor ~Normal(0.85, 0.1) clamped to [0.4, 1.0],
  so most memberships land in the low hundreds of hours (a quarter-allocation short stint runs
  ~tens; a full-allocation year-long staffing runs into the high hundreds). Open memberships
  bill through the project's target end. Drawn on its own stream, independent of `bill_rate` —
  the fixed-fee-write-off surprise (fewer billed hours than budget) is a future scenario.
- **Consulting dimensions.** `industry` mix Financial Services 0.22 / Technology 0.18 /
  Healthcare 0.16 / Retail 0.14 / Public Sector 0.12 / Manufacturing 0.12 / Energy 0.06;
  `billing_type` time_and_materials 0.55 / fixed_fee 0.30 / retainer 0.15; `priority` low 0.30 /
  medium 0.50 / high 0.20. All flat and mutually independent. Each project points at a
  `client_id` sampled uniformly from the `clients` dimension (≈half as many clients as
  projects, so most clients carry 1–2 projects and a few carry several), and `client_name` is
  that client's name denormalized onto the project.
- **Client accounts.** ~20 clients at `scale=1`; `tier` runs strategic 0.15 / growth 0.30 /
  mid 0.35 / small 0.20, `industry` follows the same `INDUSTRIES` mix, `hq_city` the same
  hub-heavy `LOCATIONS` mix, and `relationship_start_date` spans up to ~6 years before the
  window. All flat — no revenue concentration by tier is planted (a future scenario).
- **Practice split.** 6 of the 8 departments are `delivery`, 2 are `enabling`.
- **Skill / work-mode mix.** `primary_skill` is uniform within a department over that
  practice's 4-skill set; `work_mode` is a flat org-wide onsite 0.30 / hybrid 0.50 /
  remote 0.20 — both independent of every other field (no remote-concentration signal planted).
- **Hire source & prior experience.** `hire_source` is a flat org-wide mix — referral 0.28 /
  direct 0.25 / agency 0.22 / campus 0.20 / rehire 0.05 — independent of every other field (the
  "referrals churn less" cut is a future scenario). `prior_experience_years` is a
  Poisson(≈4)-shaped base plus a seniority offset of +2 years per role rung, so it trends up the
  ladder (Associates centre ~4y, Managers ~12y) while staying an *external* axis drawn
  independently of `hourly_rate`.
- **Skills-bridge mix.** Each employee carries a uniform 1–4 skills (mean ~2.5), always
  including their `primary_skill` and the rest sampled without replacement from the same
  4-skill practice set. `proficiency` runs beginner 0.35 / intermediate 0.45 / expert 0.20 and
  `certified` ≈0.30 — both flat org-wide rates on their own streams, independent of practice,
  role, and each other (no skill-depth-by-practice signal planted).
- **Review-rating skew.** `performance_reviews.rating` is a mild curve centred on ~3.6
  (Normal(3.6, 0.9) clamped and rounded to 1–5), so ratings pile at 4 then 3, thin at the tails
  — a plausibly generous review distribution. `promoted` ≈0.10. Both are drawn independently of
  attrition, practice, and tenure — the "low ratings precede termination" / "ratings ladder by
  practice" cuts are future scenarios, not planted here.
- **Expense mix.** Each project draws ~Poisson(4) expense lines; `category` runs travel 0.35 /
  meals 0.25 / lodging 0.20 / software 0.12 / subcontractor 0.08, and `amount` is a common
  lognormal (median ~$500, σ≈0.7) category-scaled — so a meal lands ~$60, lodging ~$250, travel
  ~$800, software ~$1.2k, subcontractor ~$6k, with a long right tail. `billable` ≈0.70; ~25% of
  lines carry no named employee (project-level costs), the rest name a staffed member. Flat and
  decoupled from `budget_amount` — the travel-heavy-off-site cut is a future scenario.
- **Leave mix.** Each employee draws ~Poisson(4 × tenure-years) leave spells; `leave_type` runs
  vacation 0.42 / sick 0.30 / holiday 0.15 / parental 0.08 / unpaid 0.05, with per-type spell
  lengths (median days: vacation ~4, sick/holiday ~1, unpaid ~7, parental ~45, right-skewed).
  `hours` ≈ spanned working days × 8. Flat — drawn on its own stream, independent of practice,
  season, and role (the seasonal / practice sick-leave clustering is a future scenario).
- **Billability.** `is_billable` ≈ 0.90 for delivery-practice staff, ≈ 0.35 for enabling —
  most consultants bill, most overhead staff don't (headcount-weighted, ~0.75 overall).
- **Actual billable time.** Among worked (non-no-show) entries, `time_entries.billable` runs
  ≈ 0.85 on delivery-department shifts and ≈ 0.20 on enabling ones — so utilization
  (billable ÷ worked hours) is high in delivery, low in overhead.
- **Utilization targets.** `target_utilization_pct` ladders down the seniority pyramid:
  Associate ~80 → Senior Associate ~78 → Lead ~72 → Supervisor ~63 → Manager ~55, with ±3
  jitter; only billable staff carry one.
- **Project budgets.** `budget_hours ≈ duration_days × ~32` effective billable hrs/day
  (lognormal, σ≈0.4), so roughly 2k–13k hours; `budget_amount = budget_hours × blended_rate`
  with the blended rate ~Normal($220, $25) floored at $150 — engagements land ~$0.5M–$3M.
- **Sales cycle.** `start_date − contract_signed_date` is a right-skewed lead (lognormal,
  median ≈60 days, tail to longer cycles), floored so `contract_signed_date` never predates the
  window start — most engagements sign a couple of months before kickoff, a few much earlier.
  Drawn on its own stream, independent of industry / billing_type / priority.
- **Schedule slip.** For completed projects, `actual_end_date − target_end_date` is a
  right-skewed slip (lognormal): median ~+4 days late, ranging from a few days early (~−6) to a
  long late tail (~+30). The *observed* slip is **right-truncated at the window**: a completion
  landing on/after `end_date` is censored (the project shows as `active`, not a late completion),
  so among projects that still read `completed` the visible late tail is clipped near the window
  edge — the underlying draw is unchanged, only its observable range is bounded.
- **Client satisfaction.** Completed projects score ~Normal(4.1, 0.7) clamped to [1, 5] —
  skewed high, most 4s and 5s.
- **Shift shape.** morning/afternoon/night windows roughly uniform; durations 8h dominant
  (0.70), then 10h (0.20), 12h (0.10).
- **Attendance.** ~4.6% no-show overall, driven by two independent levers that compose
  multiplicatively on the per-row probability. First the shift window: night ≈0.075,
  morning/afternoon ≈0.02–0.025 (a ~4× spread; see `scenarios/no-show-rate.md`). Second the
  scheduling lead time: a factor `clip(7·exp(−lead_days/1.75) + 0.70, 0.70, 4.8)` on that base
  that amplifies short-notice shifts and suppresses well-planned ones (see
  `scenarios/short-notice-shifts-no-show-more.md`). The lead factor averages ≈1.1 across the
  roster, so the window base rates stay the marginal-preserving centre. Clock-in jitter is
  normal with a slight late bias (mean +3 min).
- **Scheduling lead time.** `assignments.assigned_at` is the shift's `planned_start` minus a
  right-skewed lead (lognormal, median ≈7 days, tail out to a few weeks), floored at the
  employee's hire date — so `planned_start − assigned_at` (the lead time) is mostly ~a week,
  with some same-week and some far-out rosters. The lead-time *distribution* is still drawn
  flat on its own stream in `assignments` (independent of window), but no-shows now key off it
  in `time_entries` (see `scenarios/short-notice-shifts-no-show-more.md`): short-notice shifts
  (<3d) miss ≈2.9× more often than well-planned ones (≥7d).
- **Timesheet compliance.** Among worked (non-no-show) entries, `approval_status` runs
  approved ≈0.90 / pending ≈0.07 / rejected ≈0.03, and `submitted_late` ≈0.12. Flat org-wide
  rates, independent of practice, shift window, and every other field (the compliance-by-slice
  surprise is a future scenario, not planted here).
- **Timekeeping source.** Among worked entries, `entry_source` runs badge ≈0.45 / mobile ≈0.30 /
  web ≈0.18 / manual ≈0.07 — a flat org-wide mix on its own stream, independent of practice,
  shift window, and compliance (the "manual entries get corrected more" cut is a future
  scenario).
- **Overtime.** A right-skewed non-negative tail, concentrated by department: Software
  Engineering draws from Normal(0.6, 1.3) (mean ≈0.88h, ~37% of shifts 1h+ over), every other
  department from Normal(0.12, 0.45) (mean ≈0.25h). Overall mean ≈0.34h > median ≈0.15h —
  most shifts run near plan, Software Engineering supplies the blow-outs.
- **Staffing noise.** Rosters target `required_headcount` ±15%, occasionally over/under, and
  never exceed the department's employee pool.
- **Location mix.** Employees and projects are based across 6 offices, hub-heavy: New York
  0.30, Chicago 0.20, Seattle 0.16, Austin 0.14, Atlanta 0.12, Denver 0.08.
- **Project teams.** ~40 projects (at `scale=1`), each staffed with a Poisson(6)-ish team
  (min 2). `status` is **drawn** active 0.50 / completed 0.40 / on_hold 0.10, but the
  **observed** completed share is lower — ~0.30–0.33 — because right-censoring downgrades any
  drawn-`completed` project whose completion lands past the window end to `active`. About ~20%
  of drawn-completed projects flip this way (the late tail of the slip distribution overruns the
  snapshot). Mind the draw-vs-observed distinction: the *weight* is still 0.40, the *table* reads
  ~0.31 completed. `allocation_pct` is 100 (0.35) / 50 (0.30) / 75 (0.20) / 25 (0.15).
- **Membership tenure.** `rolled_on_date` skews to kickoff — a right-skewed offset off the
  project start (median ~5% of duration, tail out to ~55%), so most members join in the first
  weeks and a few augment late. On completed projects `rolled_off_date` skews to the project
  end (median ~4% of duration before `target_end_date`, tail leaving up to ~50% early). Both
  offsets are drawn independently per membership (their own child stream), unrelated to
  `allocation_pct` or to the member's other projects.
- **Leads skew senior.** Because the lead is the most senior member of a ~6-person draw,
  leads concentrate at the top rungs — ~80% are Lead / Supervisor / Manager and only a few
  percent are Associates, versus the ~50% Associate share in the workforce at large.
- **Off-site staffing.** Overall ≈24% of members are based off-site from their project, but
  the rate ladders by the project's office: New York ≈0.10 up to Denver ≈0.50 (the small
  satellites run 2–4× the hub, partly because their thin local pool forces off-site picks).
  See `scenarios/off-site-staffing-by-location.md`.

## Deliberate simplifications (intended — do not "fix")

- One `time_entries` row per assignment: no multiple punches, meal breaks, or split shifts.
- Attendance is independent per row — the no-show probability varies by shift window and
  scheduling lead time, but there is no per-employee reliability and no streaks. Likewise
  overtime depends on the department but not on the individual employee.
- Employees are rostered only in their home department (no cross-department coverage).
- **The reporting tree is a flat random senior-in-department pick.** `manager_id` is chosen
  uniformly among same-department employees of a higher `role` rung, so spans of control are
  uneven and unmodelled, the hierarchy has no controlled depth (a chain can skip rungs), a
  manager need not manage a whole rung, and reporting never crosses departments. It is
  independent of who actually staffs whom on projects (`project_members` leads are unrelated to
  `manager_id`).
- **Terminations and leave are modelled; pay is still static.** `employees.termination_date`
  records attrition, and staffing enforces it — `assignments` and `project_members` never place
  an employee before hire or after termination (rosters and project pools shrink accordingly,
  and a member who leaves mid-project rolls off on their termination date). Leave-of-absence
  spells are now modelled too: the `time_off` table records per-employee vacation / sick /
  holiday / unpaid / parental spells inside each employee's employment window, giving a truer
  utilization denominator (available = capacity − leave). What remains simplified: pay is static
  (no raises with tenure) and there are no PTO / holiday / overnight pay premiums; `time_off` is
  a standalone availability view, **not** reconciled against `shifts` / `assignments` (a spell
  can overlap a rostered shift — the two halves stay decoupled by design). Attrition itself is
  flat (~18%, independent of practice / role / tenure), and leave is flat too (no seasonal or
  per-practice clustering); those slices are future scenarios, not planted here.
- **Overtime is a non-negative clamped draw, so ~39% of worked shifts log *exactly* their
  planned hours** — `worked_hours` has a visible spike on {8, 10, 12} with a right tail. This
  "most shifts fine, a few blow out" spike-at-zero is the intended shape (see
  `scenarios/overtime-right-skew.md`), not a lattice artifact to smooth away.
- `employment_type` (full_time / part_time / contractor) is drawn independently of role and
  department, so seniority does not skew toward full-time the way it would in a real org.
- `required_headcount` is uniform on [2, 8], and shifts are spread uniformly across
  departments, calendar days, and weekday/weekend — there is no scheduling seasonality and
  no department-size differences.
- **Projects are decoupled from shifts/time_entries.** Project membership is a separate
  staffing view — there are no per-project time entries, budgets, or hours, and a member's
  `allocation_pct` doesn't reconcile against their shift roster. A project's owning
  `department_id` is independent of which departments its members come from (membership is
  cross-functional by design), and `status` / dates carry no dependency on member activity.
- **Engagement manager is a flat senior pick, no book-concentration signal.**
  `projects.engagement_manager_id` is a uniform pick among Supervisor/Manager-rung employees
  whose tenure covers the project's `start_date` (widening to Lead+, then any employed
  employee, only if that senior pool is empty at the date). It is the accountable-owner
  dimension distinct from the on-project `role_on_project = 'lead'` and from `manager_id`, but
  it carries no planted signal: no partner-concentration (a few managers owning an outsized
  book), no link to CSAT or overruns — those are future scenarios.
- **`allocation_pct` is per-project, and concurrency is not managed.** Memberships now carry
  `rolled_on_date` / `rolled_off_date`, so a member's overlapping projects (and thus a
  capacity timeline) *are* observable — but nothing enforces a capacity ceiling. The roll
  dates are drawn independently of `allocation_pct` and of the member's other memberships, so
  summing a member's `allocation_pct` across projects that overlap in time can still exceed
  100%. That over-allocation is now *detectable* by date overlap, but it is not a planted
  signal — just the absence of a capacity/scheduling model. A deliberate over-allocation
  concentrated in a slice would be a future scenario on top of these dates.
- **`location_city` is a static home office**, drawn independently of department, role and
  hire date; nobody relocates. Off-site membership is engineered via the project location's
  remote rate, not derived from any commute or relocation model.
- **Client master exists, but stays flat.** `projects.client_id` is an FK into a real
  `clients` dimension (each client carries a `tier`, `industry`, `relationship_start_date`, and
  `hq_city`), and `projects.client_name` is that client's name denormalized back onto the
  project — so multiple projects genuinely share a client, and client-concentration / tenure /
  revenue-by-tier are computable. What stays simplified: a project is assigned a client
  **uniformly at random**, so client `tier`, `industry`, and `hq_city` carry no planted signal
  (no revenue-Pareto where a few `strategic` clients hold an outsized share of billed hours —
  that is a future scenario), and the client's own `industry` is independent of the project's
  `industry` (both kept). `projects.industry` / `billing_type` / `priority` are still drawn
  independently of each other, of `department_id`, and of any project economics — flat mixes
  with no planted margin/realization/overrun signal.
- **Billability is a flat practice-level mix, not a planted signal.** `is_billable` and
  `time_entries.billable` key only off the department's `practice_type` (delivery vs enabling)
  — an *expected* split, so it lives here as a distribution, not in `scenarios/`. There is no
  per-employee reliability, and the two billable views are drawn **independently**: a
  `time_entries` row keys off its shift department's practice type, not the worker's own
  `is_billable`, so a non-billable employee can log a billable entry (and vice versa) — they
  are not reconciled. A *sharper measured* concentration, or an actual-vs-target utilization
  gap for a slice, is left as a future scenario.
- **Timesheet compliance is flat, not planted.** `approval_status` and `submitted_late` are
  drawn independently on their own stream, at flat org-wide rates with no dependency on
  practice, shift window, employee, or billability — so no revenue-leakage-by-slice signal is
  planted. The teachable surprise (late/rejected timesheets concentrating in a practice or the
  night window, echoing the no-show-by-window signal) is a future scenario
  (`/scenario:draft-or-propose`), not planted here.
- **Project economics are flat, not planted.** `budget_hours` / `budget_amount` are sized off
  duration and a blended rate, **decoupled from actual staffing and time** (no burn is
  reconciled against `bill_rate × worked hours`) — consistent with the "Projects are decoupled
  from shifts/time_entries" note. `actual_end_date` slip and `client_satisfaction` are drawn
  flat: slip does **not** concentrate in a practice, and CSAT is independent of budget,
  overrun, or staffing. The teachable surprises these set up — **fixed-fee projects overrun**
  while T&M don't, **Software Engineering slips its schedule** (echoing the overtime tail), and
  **CSAT dips for overrun/thin-staffed projects** — are deliberately *not* planted here; they
  are future scenarios (`/scenario:draft-or-propose`).
- **Right-censoring is the cross-collection completion convention (cf. `hotel`).** A completed
  event whose end lands past the snapshot window is *unobservable*, so `labor` right-censors it:
  a project drawn `completed` past `end_date` is downgraded to `active` with no recorded outcome
  (see the "Actual end is right-censored" invariant). `streaming` applies the same convention on
  the subscription side (an end past the window reads as still-active). This is a deliberate,
  shared modeling choice — a project's `actual_end_date` is an *observed* event and must sit
  inside the window, even though its `target_end_date` (a plan) may spill past it. **`hotel` is
  the documented exception:** a `stays` row is a completed-revenue record, so its checkout is
  allowed to *spill* past the window rather than be censored (a booked stay that checks out after
  the snapshot still booked the revenue) — intentional divergence, not an inconsistency to
  "fix".
- **Expenses are a decoupled cost view.** `expenses` lines price project cost beyond labor
  (T&E, subcontractor, software), but they are **not** reconciled against `budget_amount` (which
  prices labor only) or against `billed_hours` — category, amount, billability, and member
  attribution are drawn flat and independently. The travel-heavy-spend-on-off-site-projects cut
  (echoing `off-site-staffing-by-location`) is a future scenario, not planted here.
- **Bill-rate markup is flat by role; realization now varies by billing_type.**
  `standard_bill_rate` markup ladders by role only (no per-practice compression), so
  margin-by-practice still looks flat by design — a natural future scenario, a realism
  dimension only today. `bill_rate` realization, by contrast, is **no longer flat**: its mean
  is keyed off `billing_type` (fixed-fee realizes ~12pt below T&M — a planted signal, see
  `scenarios/fixed-fee-engagements-realize-lower.md`), though it stays independent of
  `industry` and client. Non-billable members do carry a null
  `bill_rate` (the billable/non-billable split is honoured). Project revenue is now *computable*
  staffing-side as `Σ billed_hours × bill_rate` (both set for billable members), so the earlier
  "approximable but not reconciled" gap is closed on the staffing side — but `billed_hours` is
  still deliberately **decoupled** from `time_entries`: there is no link from a worked clock
  entry to a project, so staffing-side revenue is not reconciled against actual delivery time.

## How to review

```sql
-- no-show rate ≈ 0.046, and null clock-ins are exactly the no-shows
select avg(no_show::int)                              as no_show_rate,       -- ≈ 0.046
       count(*) filter (where clock_in is null)       as null_clock_ins,
       count(*) filter (where no_show)                as no_show_rows        -- == null_clock_ins
from time_entries;

-- worked never below planned for shifts that happened
select count(*) filter (where worked_hours < planned_hours) as impossible    -- expect 0
from time_entries where not no_show;

-- rostering respects department: expect 0 mismatches
select count(*) as cross_dept
from assignments a
join employees e using (employee_id)
join shifts s on s.shift_id = a.shift_id
where e.department_id <> s.department_id;                                     -- expect 0

-- rostering respects employment: nobody worked before hire or after leaving
select count(*) as out_of_tenure
from assignments a
join employees e using (employee_id)
join shifts s on s.shift_id = a.shift_id
where s.planned_start::date < e.hire_date
   or (e.termination_date is not null and s.planned_start::date >= e.termination_date); -- expect 0

-- exactly one lead per project, and off-site share ladders by project location
select count(*) filter (where role_on_project = 'lead') as leads,            -- == #projects
       (select count(*) from projects)                  as projects
from project_members;

-- leads skew senior: Associates (the junior rung) almost never lead a project
select e.role, count(*) as leads
from project_members m
join employees e using (employee_id)
where m.role_on_project = 'lead'
group by e.role order by leads desc;   -- concentrated in Lead/Supervisor/Manager, ~0 Associate

select p.location_city, avg((e.location_city <> p.location_city)::int) as offsite_rate
from project_members m
join projects p using (project_id)
join employees e using (employee_id)
group by p.location_city order by offsite_rate;         -- New York ≈0.10 … Denver ≈0.50
```
