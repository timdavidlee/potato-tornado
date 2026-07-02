# A department's base rate can outweigh a seniority rung

- **Signal:** grouped by role, pay rises cleanly up the ladder (Associate →
  Manager). But that ladder is *within* a department: a promotion is worth **+18%**
  per rung, while the department base rate spans **$21–$28 (~33%)** — a wider gap
  than a single rung. So an **Associate in the highest-base department (Maintenance,
  $28) out-earns a Senior Associate in the lowest-base department (Housekeeping,
  $21)** — the more junior employee is paid more.
- **Tables:** `employees.hourly_rate`, `employees.role`, `employees.department_id`,
  `departments.base_hourly_rate`
- **Magnitude:** `hourly_rate = department_base × (1 + 0.18 × role_index) × jitter`
  (jitter ±6%, clamped). One rung ≈ ×1.18; the base spread ≈ ×1.33. Associate @
  Maintenance ≈ **$28** vs Senior Associate @ Housekeeping ≈ **$25** — the junior
  role wins by ~$3/hr.

The overall "pay rises with seniority" ladder is real and monotone, but pooling
roles across departments hides that two effects stack multiplicatively and the
department term is the larger one. The teaching point is that a naive "sort by
seniority to rank pay" fails at the margins: because the base spread exceeds a
single rung, you must control for department before comparing roles (and vice
versa). It's the pay counterpart to the slice stories elsewhere in the collection
(`scenarios/no-show-rate.md`, `scenarios/overtime-right-skew.md`).

## How to find it

```sql
-- the ladder is monotone once you hold department fixed (or on average)
select role, avg(hourly_rate) from employees group by role;   -- increases up the ladder

-- but department base outweighs a rung: a junior in the top-base department
-- out-earns a more-senior colleague in the bottom-base department
select d.name, e.role, avg(e.hourly_rate) as avg_rate
from employees e
join departments d using (department_id)
where (d.name = 'Maintenance'   and e.role = 'Associate')        -- ≈ 28
   or (d.name = 'Housekeeping'  and e.role = 'Senior Associate') -- ≈ 25
group by d.name, e.role;                                          -- Associate row is higher
```
