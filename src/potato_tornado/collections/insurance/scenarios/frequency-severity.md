# Frequency-severity: few policies claim, and claim cost is heavy-tailed

- **Signal:** claiming is **rare** (a minority of policies ever file), but among the
  claims that are filed, the payout is **heavy-tailed** — most are modest, a few are
  very large. Two separate distributions: *whether* a policy claims (a Poisson event
  keyed to risk tier) and *how much* it costs (a right-skew severity).
- **Tables:** `claims.policy_id`, `claims.reported_amount`,
  `claim_payments.paid_amount`, `policies.policy_id`.
- **Magnitude:** ≈ **11%** of policies file ≥1 claim; `reported_amount` median ≈
  **\$6.7k**, p95 ≈ **\$31k**, max past **\$50k** (a base lognormal with σ ≈ 1.0, whose
  median/p95 the ×2.2 litigation loading on the ~11% litigated claims nudges up a few
  points from ≈\$6.4k — see `scenarios/litigation-tax.md`). The mean sits well above the
  median — the hallmark of the fat tail.

Claim frequency is a per-policy `Poisson(λ × term_years)` with λ set by the holder's
risk tier, so most policies contribute zero claims; severity is an independent
lognormal draw. The teaching point is that these two must be modelled — and queried —
separately: a claim *rate* (a count over policies) is a different question from a
claim *cost* (a quantile over amounts), and the cost side is dominated by a handful
of extreme losses, so a mean is misleading (report a median and a p95).

## How to find it

```sql
-- frequency: only a minority of policies ever claim
select count(distinct c.policy_id)::float / (select count(*) from policies) as claim_rate  -- ≈ 0.11
from claims c;

-- severity: heavy right tail (mean >> median), long p95/max
select quantile_cont(reported_amount, 0.5)  as p50,   -- ≈ 6700
       quantile_cont(reported_amount, 0.95) as p95,   -- ≈ 31000
       max(reported_amount)                  as max_,  -- past 50000
       avg(reported_amount)                  as mean_  -- well above p50
from claims;
```
