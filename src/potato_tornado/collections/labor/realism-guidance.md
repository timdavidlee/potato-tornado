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
- **Project bill rate is a realized discount.** `project_members.bill_rate > 0` and lies in
  `[0.6, 1.0] ×` the member's `employees.standard_bill_rate` — a member is never billed above
  their standard list rate.
- **Project catalogs.** `projects.client_name` is an entity company name;
  `projects.industry ∈ INDUSTRIES`, `projects.billing_type ∈ BILLING_TYPES`,
  `projects.priority ∈ PROJECT_PRIORITIES` are all from their fixed catalogs.
- **Practice classification.** `departments.practice_type ∈ {delivery, enabling}`, and it is
  `enabling` for exactly the two overhead functions (`ENABLING_DEPARTMENTS` = Project
  Management, IT Support Services) and `delivery` for the other six.
- **Skill matches practice.** `employees.primary_skill` is one of `SKILLS_BY_DEPARTMENT` for
  the employee's own department — a consultant's skill always belongs to their practice.
  `employees.work_mode ∈ {onsite, hybrid, remote}`.
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
- **Timesheet fields close with the worked entry.** `time_entries.approval_status` and
  `time_entries.submitted_late` are populated **iff** `no_show = false` — both are `null` on
  no-show rows (no timesheet to submit or approve). `approval_status ∈ {approved, pending,
  rejected}`.
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
  `start_date` is in `[start_date, end_date)`, but `target_end_date` may fall past the window
  end (it's a target, not an actual).
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
  another `employees` row.

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
- **Realization.** `project_members.bill_rate = standard_bill_rate × realization`, realization
  ~Normal(0.85, 0.06) clamped to [0.6, 1.0] — mean ≈ 0.85, i.e. members bill at ~85% of list.
  Flat across billing types and clients (the depressed-realization-by-billing-type surprise is
  a future scenario, not planted here).
- **Capacity mix.** `weekly_capacity_hours` follows the employment mix: ~30% part_time at 20h,
  the rest at 40h — the utilization denominator.
- **Consulting dimensions.** `industry` mix Financial Services 0.22 / Technology 0.18 /
  Healthcare 0.16 / Retail 0.14 / Public Sector 0.12 / Manufacturing 0.12 / Energy 0.06;
  `billing_type` time_and_materials 0.55 / fixed_fee 0.30 / retainer 0.15; `priority` low 0.30 /
  medium 0.50 / high 0.20. All flat and mutually independent. `client_name` is an entity
  company name, drawn per project.
- **Practice split.** 6 of the 8 departments are `delivery`, 2 are `enabling`.
- **Skill / work-mode mix.** `primary_skill` is uniform within a department over that
  practice's 4-skill set; `work_mode` is a flat org-wide onsite 0.30 / hybrid 0.50 /
  remote 0.20 — both independent of every other field (no remote-concentration signal planted).
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
- **Schedule slip.** For completed projects, `actual_end_date − target_end_date` is a
  right-skewed slip (lognormal): median ~+4 days late, ranging from a few days early (~−6) to a
  long late tail (~+30).
- **Client satisfaction.** Completed projects score ~Normal(4.1, 0.7) clamped to [1, 5] —
  skewed high, most 4s and 5s.
- **Shift shape.** morning/afternoon/night windows roughly uniform; durations 8h dominant
  (0.70), then 10h (0.20), 12h (0.10).
- **Attendance.** ~4% no-show overall, but keyed to the shift window: night ≈0.075,
  morning/afternoon ≈0.02–0.025 (roughly a 4× spread). Clock-in jitter is normal with a
  slight late bias (mean +3 min).
- **Timesheet compliance.** Among worked (non-no-show) entries, `approval_status` runs
  approved ≈0.90 / pending ≈0.07 / rejected ≈0.03, and `submitted_late` ≈0.12. Flat org-wide
  rates, independent of practice, shift window, and every other field (the compliance-by-slice
  surprise is a future scenario, not planted here).
- **Overtime.** A right-skewed non-negative tail, concentrated by department: Software
  Engineering draws from Normal(0.6, 1.3) (mean ≈0.88h, ~37% of shifts 1h+ over), every other
  department from Normal(0.12, 0.45) (mean ≈0.25h). Overall mean ≈0.34h > median ≈0.15h —
  most shifts run near plan, Software Engineering supplies the blow-outs.
- **Staffing noise.** Rosters target `required_headcount` ±15%, occasionally over/under, and
  never exceed the department's employee pool.
- **Location mix.** Employees and projects are based across 6 offices, hub-heavy: New York
  0.30, Chicago 0.20, Seattle 0.16, Austin 0.14, Atlanta 0.12, Denver 0.08.
- **Project teams.** ~40 projects (at `scale=1`), each staffed with a Poisson(6)-ish team
  (min 2). `status` is active 0.50 / completed 0.40 / on_hold 0.10. `allocation_pct` is
  100 (0.35) / 50 (0.30) / 75 (0.20) / 25 (0.15).
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
- Attendance is independent per row — the no-show probability varies by shift window, but
  there is no per-employee reliability and no streaks. Likewise overtime depends on the
  department but not on the individual employee.
- Employees are rostered only in their home department (no cross-department coverage).
- **The reporting tree is a flat random senior-in-department pick.** `manager_id` is chosen
  uniformly among same-department employees of a higher `role` rung, so spans of control are
  uneven and unmodelled, the hierarchy has no controlled depth (a chain can skip rungs), a
  manager need not manage a whole rung, and reporting never crosses departments. It is
  independent of who actually staffs whom on projects (`project_members` leads are unrelated to
  `manager_id`).
- **Terminations are modelled; other leave is not.** `employees.termination_date` records
  attrition, and staffing enforces it — `assignments` and `project_members` never place an
  employee before hire or after termination (rosters and project pools shrink accordingly, and
  a member who leaves mid-project rolls off on their termination date). But there is no PTO /
  holiday / leave-of-absence spell (a terminated employee is simply absent from all dates after
  their leaving date), pay is static (no raises with tenure), and there are no PTO / holiday /
  overnight premiums. Attrition itself is flat (~18%, independent of practice / role / tenure);
  a high-turnover slice is a future scenario, not planted here.
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
- **No client master.** `projects.client_name` is a bare company-name string drawn per
  project, not an FK to a `clients` table — the same name can recur across unrelated projects
  by chance and carries no attributes of its own. `industry` / `billing_type` / `priority` are
  drawn independently of each other, of `department_id`, and of any project economics — flat
  mixes with no planted margin/realization/overrun signal (those are future scenarios). A real
  client dimension with its own attributes would be a new table, not a column.
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
- **Bill economics are flat, not planted.** `standard_bill_rate` markup ladders by role only
  (no per-practice compression) and `bill_rate` realization is a uniform ~0.85 discount
  independent of `billing_type`, `industry`, or client — so margin-by-practice and
  realization-by-billing-type look flat by design. These are the natural shortlist for future
  scenarios; today they are realism dimensions only. There is no project budget/burn, no
  billable/non-billable split, and no link from `time_entries` to a project, so `bill_rate ×
  hours` revenue can be *approximated* but not reconciled against actual delivery time.

## How to review

```sql
-- no-show rate ≈ 0.04, and null clock-ins are exactly the no-shows
select avg(no_show::int)                              as no_show_rate,       -- ≈ 0.04
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
