# Subrogation recovery is entirely an auto-line lever

- **Signal:** every dollar of subrogation recovery comes from the **auto** book —
  home and renters claims recover **nothing**. So a net-of-subrogation loss ratio
  (gross paid vs. paid − recovery) improves *only* for auto; for home and renters the
  net ratio equals the gross ratio exactly. The savings are 100% concentrated in one
  product line.
- **Tables:** `claim_payments.subrogation_recovery_amount`, `claim_payments.paid_amount`,
  `claims.at_fault`, `claims.policy_id`, `policies.product`, `policies.annual_premium`
  (join `claim_payments → claims → policies` and slice by `product`).
- **Magnitude (measured, seed 7, scale 1.0):** auto's share of total recovery ≈
  **100%** (1.000, and it stays 1.000 across seeds 7 / 13 / 21). ≈ **10%** of *auto*
  settled claims carry a positive recovery (26 of 259; **0 of 121** home, **0 of 90**
  renters); total recovery ≈ **3–6%** of auto paid (0.033 / 0.062 / 0.046 across those
  three seeds). Net-of-subro loss ratio for auto ≈ **0.57 vs 0.59 gross** (a ~2 pp / ~3%
  relative shave); home ≈ 0.57 and renters run high/noisy, but for both **net == gross**
  to the cent. (At the scenario test's `scale=0.5`, seed 7: 12 recovered claims, all auto,
  auto share still 1.000 — small-n but the concentration is structural, not noise.)

Subrogation is the insurer recovering part of a payout from an **at-fault third party**,
so it is only plausible when fault can be pinned on someone else. In this book
`claims.at_fault` is populated **iff** the policy's `product = 'auto'` (a liability
posture only auto claims carry — it is null on home and renters), and recovery is gated
on the claim being explicitly **not-at-fault** (`at_fault is False`). Those two rules
compose: no non-auto claim is ever eligible, so 100% of recovered dollars land in the
auto line. The teaching point is that a net-of-subrogation loss ratio is a
**product-line question, not a blended one** — compute it across the whole book and the
recovery looks like a small, uniform few-percent haircut; slice by product and you see
the entire benefit is an auto-only lever, while home and renters are untouched. It pairs
with `loss-ratio-rises-with-risk-tier.md` (which slices the *gross* ratio by tier): here
the surprise is *where the recovery offset concentrates*, not what drives gross losses.
This is already produced by the generator — it is the emergent, quantified consequence of
the `at_fault`-nullity and subrogation-eligibility invariants, which name the gate but
never document the product-line concentration or its net-loss-ratio magnitude.

## How to find it

```sql
-- 1) every dollar of subrogation recovery comes from the auto line
select p.product,
       count(*)                                                    as settled_claims,
       count(*) filter (where pay.subrogation_recovery_amount > 0) as n_recovered,
       round(coalesce(sum(pay.subrogation_recovery_amount), 0), 0) as total_recovery
from claim_payments pay
join claims   c using (claim_id)      -- settled claims only (payment exists iff settled)
join policies p using (policy_id)
group by p.product order by p.product;
-- auto  ≈ 259 settled, ≈ 26 recovered (~10%), ~$76k recovered
-- home  ≈ 121 settled,   0 recovered,          $0
-- renters ≈ 90 settled,  0 recovered,          $0   -> auto share of recovery = 1.00

-- 2) net-of-subrogation loss ratio moves ONLY for auto
select p.product,
       round(sum(pay.paid_amount) / prem.prem, 3)                                        as gross_lr,
       round((sum(pay.paid_amount) - sum(coalesce(pay.subrogation_recovery_amount, 0)))
             / prem.prem, 3)                                                             as net_lr
from claim_payments pay
join claims   c using (claim_id)
join policies p using (policy_id)
join (select product, sum(annual_premium) as prem from policies group by product) prem
     using (product)
group by p.product, prem.prem
order by p.product;
-- auto:    gross ≈ 0.587  net ≈ 0.567   (the ~2 pp gap is the subrogation offset)
-- home:    gross ≈ net    (0.572 = 0.572, no recovery)
-- renters: gross ≈ net    (identical, no recovery)
```
