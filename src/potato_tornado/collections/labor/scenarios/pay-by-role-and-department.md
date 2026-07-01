# Pay rises with seniority and varies by department

- **Signal:** `hourly_rate` increases monotonically with the role ladder
  (Associate → Manager) and shifts up or down with the employee's department
  base rate.
- **Tables:** `employees.hourly_rate`, `employees.role`,
  `employees.department_id`, `departments.base_hourly_rate`
- **Magnitude:** a seniority multiplier of `1 + 0.18 × role_index` (Manager ≈
  1.72× an Associate in the same department), on top of a department base rate of
  \$21–\$28, times a small ±6% jitter.

Rate is `department_base × role_multiplier × jitter`, so two effects stack: the
role ladder and the department. Grouping by role shows a clean monotone ladder;
grouping by department shows the base-rate offset. A student should be able to
separate the two factors — the jitter is small enough that the ordering holds.

## How to find it

```sql
select role, avg(hourly_rate)          -- monotone increasing up the ladder
from employees group by role;

select department_id, avg(hourly_rate) -- tracks departments.base_hourly_rate
from employees group by department_id;
```
