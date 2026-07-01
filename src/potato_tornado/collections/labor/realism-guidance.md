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
- **Hire dates are in-window.** `hire_date ≤ end_date` (and no later); it may fall up to
  ~5 years before `start_date`.
- **Referential integrity.** `assignments.employee_id ∈ employees`,
  `assignments.shift_id ∈ shifts`, `time_entries` FKs resolve.

## Distributions & mixes (should look like the real world)

- **Role pyramid.** Associate 0.50 → Senior Associate 0.25 → Lead 0.13 → Supervisor 0.08 →
  Manager 0.04. Most staff are junior.
- **Employment mix.** full_time 0.60 / part_time 0.30 / contractor 0.10.
- **Pay ladder.** Department base $21–28/hr; +18% per seniority rung; ±6% jitter clamped to
  [0.85, 1.2]×.
- **Shift shape.** morning/afternoon/night windows roughly uniform; durations 8h dominant
  (0.70), then 10h (0.20), 12h (0.10).
- **Attendance.** ~4% no-show (Bernoulli p=0.96). Clock-in jitter is normal with a slight
  late bias (mean +3 min). Overtime is a right-skewed non-negative tail (mean ≈0.15h) — most
  shifts run near plan, a few run long.
- **Staffing noise.** Rosters target `required_headcount` ±15%, occasionally over/under, and
  never exceed the department's employee pool.

## Deliberate simplifications (intended — do not "fix")

- One `time_entries` row per assignment: no multiple punches, meal breaks, or split shifts.
- Attendance is independent per row — no per-employee reliability, no streaks.
- Employees are rostered only in their home department (no cross-department coverage).
- No terminations or leave: every employee is active across the whole window, pay is static
  (no raises with tenure), and there are no PTO/holiday/overnight premiums.

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
```
