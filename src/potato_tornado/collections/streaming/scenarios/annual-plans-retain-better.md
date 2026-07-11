# Annual subscribers retain far better than monthly

- **Signal:** the minority of subscribers on an `annual` billing cycle cancel at a
  fraction of the monthly rate and, when they do leave, last longer first.
- **Tables:** `subscriptions.billing_cycle`, `subscriptions.status`,
  `subscriptions.start_date`, `subscriptions.end_date`
- **Magnitude:** cancelled-rate ≈ `monthly` 0.21 vs `annual` 0.06 (~3× lower);
  among cancelled subs, mean tenure ≈ `monthly` 5.3 months vs `annual` 8.6 months.
  Only ~20% of subscribers are on annual billing.

The commitment device is the point: annual billing both lowers the cancel
probability and lengthens tenure (the same channel/billing multipliers drive
`status` and the tenure that sets `end_date`). It pairs with
`paid-channels-churn-faster.md` — both are cuts of the same non-flat churn model —
and sets up a "which lever moves retention most" comparison between an acquisition
attribute and a billing attribute.

## How to find it

```sql
-- annual churns far less than monthly, and lasts longer before it does.
select billing_cycle,
       avg((status = 'cancelled')::int)                                    as cancel_rate,
       avg(date_diff('day', start_date, end_date) / 30.0)
         filter (where status = 'cancelled')                               as mean_tenure_months
from subscriptions
group by billing_cycle;   -- monthly ~0.21 / 5.3mo, annual ~0.06 / 8.6mo
```
