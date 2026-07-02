# The adjudication funnel: reported vs paid

- **Signal:** aggregate paid runs well below aggregate reported, and the gap has
  three distinct causes: some claims are **denied** (paid \\$0, no payment row),
  **partials** pay a fraction of what was reported, and even **approved** claims net
  out the deductible and are capped at the coverage limit. A student must left-join
  claims to payments and treat the missing side as \\$0 to see it.
- **Tables:** `claims.status`, `claims.reported_amount`, `claim_payments.paid_amount`
  (a payment row exists **iff** `status ∈ {approved, partial}`).
- **Magnitude:** adjudication mix ≈ **approved 0.61 / partial 0.18 / denied 0.13 /
  open 0.08**; total paid ≈ **66%** of total reported. Denied + open (~21% of claims)
  contribute \\$0; partials pay ≈ 0.3–0.8× the approved-equivalent.

Only settled (`approved`/`partial`) claims produce a `claim_payments` row, so the
join is where the funnel lives — an inner join silently drops the \\$0 outcomes and
overstates the payout rate. The teaching point is the difference between *reported*
(what was claimed) and *paid* (what the insurer actually disbursed), and that the
shortfall decomposes into denials, partial settlements, and deductible/limit netting —
the plan-vs-actual story on a single claim.

## How to find it

```sql
-- adjudication mix
select status, count(*)::float / sum(count(*)) over () as share
from claims group by status;                         -- approved ≈ .61, partial ≈ .18, denied ≈ .13, open ≈ .08

-- paid vs reported: left join so denied/open count as $0
select sum(coalesce(pay.paid_amount, 0)) / sum(c.reported_amount) as paid_over_reported  -- ≈ 0.66
from claims c
left join claim_payments pay using (claim_id);
```
