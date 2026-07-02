# Satellite projects lean on off-site staff; the hub staffs locally

- **Signal:** a project's members are mostly based at the project's own location,
  but the *off-site share* is not uniform — it rises as the project's office gets
  smaller. Projects run from the **New York** hub are staffed almost entirely
  locally (~10% off-site), while projects at the small satellites (**Atlanta**,
  **Denver**) are roughly **half** off-site. Off-site means the member's
  `employees.location_city` differs from the project's `projects.location_city`.
- **Tables:** `project_members.employee_id`, `projects.location_city`,
  `employees.location_city`
- **Magnitude:** overall off-site rate ≈ **0.24**, but by project location it
  spans a ladder set by `REMOTE_RATE_BY_LOCATION`: New York ≈ 0.10, Chicago ≈
  0.18, Seattle ≈ 0.22, Austin ≈ 0.30, Atlanta ≈ 0.40, Denver ≈ 0.50. Realized
  rates skew a touch higher at the small offices because their thin local pool
  forces extra off-site picks. The satellites run **2–4×** the hub's off-site rate.

Membership is cross-functional — projects pull from the whole workforce, unlike
shifts, which roster only their own department. So the natural question is "where
do project members actually sit?" The top-line off-site rate looks like a single
mild number; the teaching point is that it decomposes by the project's office.
The hub has a deep local bench and staffs on-site; the satellites can't, so they
reach across locations. A naive "~a quarter of people are remote" misses that the
remote burden is concentrated on the small sites — control for
`projects.location_city` before reasoning about it. It's the location counterpart
to the window/department slice stories (`scenarios/no-show-rate.md`,
`scenarios/overtime-right-skew.md`).

## How to find it

```sql
-- off-site share overall (≈ 0.24) and by the project's location
select p.location_city,
       avg((e.location_city <> p.location_city)::int) as offsite_rate,  -- NY ≈ 0.10 … Denver ≈ 0.50
       count(*)                                       as members
from project_members m
join projects  p using (project_id)
join employees e using (employee_id)
group by p.location_city
order by offsite_rate;   -- New York lowest, the small satellites highest
```
