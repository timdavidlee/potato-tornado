# Standard is the most popular subscription tier

- **Signal:** subscribers pick the mid-tier `Standard` plan about half the time,
  with `Basic` and `Premium` splitting the rest — a classic middle-anchored plan mix.
- **Tables:** `subscriptions.plan`, `plans.plan`
- **Magnitude:** Standard ≈ 50%, Basic ≈ 30%, Premium ≈ 20%.

The plan mix is the collection's core subscription signal: the mid tier anchors
the ladder, a common outcome of three-tier pricing. Joining `subscriptions` to
`plans` also lets an analyst turn the mix into recurring revenue by tier.

## How to find it

```sql
select plan, count(*) * 1.0 / sum(count(*)) over () as share
from subscriptions
group by plan;                       -- Standard ≈ 0.50, Basic ≈ 0.30, Premium ≈ 0.20
```
