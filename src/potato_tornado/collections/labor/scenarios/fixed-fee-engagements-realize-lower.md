# Fixed-fee engagements realize a lower rate

- **Signal:** members bill to the client at ~85% of their standard list rate on
  average (realization = `bill_rate ÷ standard_bill_rate`), but that discount is
  not uniform across the commercial model — **fixed-fee** engagements realize a
  materially *lower* rate than **time-and-materials** work. On a fixed price the
  firm absorbs overruns, so effective realized rate erodes; on T&M every hour is
  billed at rate. The headline ~85% is a blend that hides the gap.
- **Tables:** `project_members.bill_rate`, `employees.standard_bill_rate`
  (realization = `bill_rate ÷ standard_bill_rate`), sliced by
  `projects.billing_type` (join `project_members`→`projects` on `project_id`,
  `project_members`→`employees` on `employee_id`)
- **Magnitude (planted; measured at seed=7, scale=0.5):** `time_and_materials`
  realization ≈ **0.89**, `retainer` ≈ **0.86**, `fixed_fee` ≈ **0.77** — a
  **~12 point** T&M-vs-fixed-fee spread — while the overall billable-member
  realization stays ≈ **0.85** (unchanged from the pre-plant 0.85). All values stay
  inside the `[0.6, 1.0] × standard_bill_rate` invariant band (observed min ≈ 0.68).

Only client-billable members carry a `bill_rate` (bench / overhead members are
null), so the realization ratio is defined exactly on the billable population.
The teaching point is that the top-line realization number looks like a single
firm-wide discount, but slicing by `billing_type` reveals *where the rate leaks*:
fixed-fee work quietly realizes less because scope creep comes out of margin, not
the invoice. It is the revenue-model counterpart to the slice stories elsewhere
in the collection (`scenarios/no-show-rate.md`,
`scenarios/overtime-right-skew.md`) — a flat average that decomposes sharply once
you control for the right dimension, and the first scenario to exercise the
consulting-economics columns (`bill_rate`, `standard_bill_rate`, `billing_type`).

**Current state:** planted in `project_members.py`. The realization discount is
still drawn on its own child stream (`Normal(mean, 0.06)` clamped to `[0.6, 1.0]`),
but its *mean* is now keyed off the project's `billing_type` via
`_REALIZATION_MEAN_BY_BILLING` (`time_and_materials` 0.89 / `retainer` 0.85 /
`fixed_fee` 0.78). Only the per-row `loc` of the same normal draw changes — the
draw count is unchanged, so determinism holds — and the clamp keeps every rate in
the `[0.6, 1.0] × standard_bill_rate` band. The type means blend back (weights T&M
0.55 / fixed_fee 0.30 / retainer 0.15) to the ~0.85 firm-wide mean, so the headline
realization is preserved while the slice-by-`billing_type` gap opens up. Its natural
partner surprise — fixed-fee projects also billing *fewer* hours than budgeted
(write-offs) — is a separate future scenario.

## How to find it

```sql
-- realized rate by commercial model; fixed-fee should sit well below T&M.
-- realization = negotiated project bill_rate / employee's standard list rate,
-- defined only for billable members (bill_rate is null for non-billable).
select p.billing_type,
       count(*)                                    as billable_members,
       avg(m.bill_rate / e.standard_bill_rate)     as realization  -- T&M ~0.90, fixed_fee ~0.78
from project_members m
join projects  p using (project_id)
join employees e using (employee_id)
where m.bill_rate is not null
group by p.billing_type
order by realization desc;                          -- time_and_materials on top, fixed_fee last

-- overall realization is ~0.85, hiding the split above
select avg(m.bill_rate / e.standard_bill_rate) as overall_realization  -- ≈ 0.85
from project_members m
join employees e using (employee_id)
where m.bill_rate is not null;
```
