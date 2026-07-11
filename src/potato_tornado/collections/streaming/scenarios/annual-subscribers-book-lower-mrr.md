# Your stickiest cohort books the least monthly revenue

- **Signal:** annual subscribers book a *lower* monthly recurring revenue than
  monthly subscribers — the "2 months free" discount — even though they churn at a
  fraction of the monthly rate. Ranking cohorts by MRR therefore under-values the
  best-retained segment.
- **Tables:** `subscriptions.mrr`, `subscriptions.billing_cycle`,
  `subscriptions.status`
- **Magnitude:** mean `mrr` ≈ **$11.3** annual vs ≈ **$13.9** monthly (ratio ≈ 0.81,
  near the 10/12 annual factor — a ~19% lower booked MRR); cancelled-rate ≈ **0.06**
  annual vs ≈ **0.21** monthly (~3× lower). Only ~20% of subscribers are on annual
  billing.

`mrr` is derived from the plan price and cadence: an annual plan is priced at 10×
the monthly rate ("2 months free"), so its monthly-equivalent MRR is
`monthly_price × 10/12` — structurally below the monthly figure. The *same* billing
lever that discounts the revenue also drives retention up (annual cancels far less
and lasts longer — see `annual-plans-retain-better.md`). Net: the lowest-MRR cohort
is the stickiest, so its expected lifetime value (MRR × retention) is the *highest*.
The teaching point is that **MRR alone misranks cohorts** — read flat, it flags
annual as your weakest revenue segment when it is actually your strongest by
lifetime value. This is the revenue/discount face of the annual story; the churn
face lives in `annual-plans-retain-better.md`.

## How to find it

```sql
-- annual books ~17% less MRR per sub, yet cancels at ~1/3 the monthly rate.
select billing_cycle,
       count(*)                             as subs,
       avg(mrr)                             as mean_mrr,     -- annual ~11.3, monthly ~13.9
       avg((status = 'cancelled')::int)     as cancel_rate   -- annual ~0.06, monthly ~0.21
from subscriptions
group by billing_cycle;
-- the cohort with the LOWER mean_mrr also has the LOWER cancel_rate -> MRR inverts value
```
