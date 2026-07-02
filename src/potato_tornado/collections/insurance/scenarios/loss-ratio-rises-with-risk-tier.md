# Loss ratio rises with risk tier

- **Signal:** the **loss ratio** (Σ paid ÷ Σ premium) climbs steeply from the
  preferred tier to the high-risk tier. High-risk policyholders pay more premium, but
  they claim so much more often that payouts outrun the extra premium — the tier is
  underwriting-negative relative to preferred.
- **Tables:** `claim_payments.paid_amount`, `policies.annual_premium`,
  `policyholders.risk_tier` (join `payments → claims → policies → policyholders`).
- **Magnitude:** overall loss ratio ≈ **0.62**; by tier ≈ **preferred 0.43 /
  standard 0.67 / high_risk 0.79** — the high-risk book runs ~1.8× the preferred loss
  ratio. (The standard→high_risk step is narrow relative to seed-to-seed noise and can
  invert on a given run; preferred < high_risk is robust.)

Risk tier drives two knobs in opposite-sized steps: the premium multiplier (0.70 /
1.00 / 1.75) and the annual claim rate λ (0.09 / 0.18 / 0.42). Frequency rises ~4.7×
across the ladder while premium rises only ~2.5×, so the ratio of paid-to-premium
widens as risk increases. The teaching point is that a portfolio's health is a
*ratio*, not a level: high-risk policies bring in the most premium per policy yet are
the least profitable, which only surfaces when you divide paid by premium within each
tier — the classic plan-vs-actual read on an insurance book.

## How to find it

```sql
select ph.risk_tier,
       sum(pay.paid_amount) / sum_prem.prem as loss_ratio   -- 0.43 / 0.67 / 0.79
from claim_payments pay
join claims c        using (claim_id)
join policies p      using (policy_id)
join policyholders ph using (policyholder_id)
join (
  select ph2.risk_tier, sum(p2.annual_premium) as prem
  from policies p2 join policyholders ph2 using (policyholder_id)
  group by ph2.risk_tier
) sum_prem using (risk_tier)
group by ph.risk_tier, sum_prem.prem
order by loss_ratio;
```
