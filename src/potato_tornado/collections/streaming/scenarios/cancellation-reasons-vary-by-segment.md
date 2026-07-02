# Why subscribers cancel depends on their segment

- **Signal:** the stated `cancel_reason` is not uniform across cancellations — it
  skews by segment. `content` dominates churn in narrow-catalogue regions (Japan,
  India), while `price` is a much larger share of churn on the entry `Basic` tier.
- **Tables:** `subscriptions.cancel_reason`, `subscriptions.status`,
  `subscriptions.plan`, `subscribers.region` (join on `subscriber_id`)
- **Magnitude:** `content` is the **top** reason in JP/IN cancellations (≈0.39 of
  them) vs ≈0.16 elsewhere; `price` is ≈0.44 of `Basic` cancellations vs ≈0.28 on
  the higher tiers. Reason is null for active subscriptions.

`cancel_reason` is populated only when `status = 'cancelled'`, and its per-row
weights are boosted by segment: narrow-catalogue markets (the same JP/IN density
tail from `catalog-size-varies-by-region.md`) lean on `content`, and the cheapest
plan leans on `price`. The teaching point is to connect *who* churns (the other
churn scenarios) to *why* — and to notice the "content" complaint tracks the
region licensing gap, tying the churn story back to the catalogue-size story.

## How to find it

```sql
-- content is the modal complaint where the catalogue is thin (JP, IN)…
select case when region in ('JP','IN') then 'narrow' else 'rest' end as market,
       avg((cancel_reason = 'content')::int)                          as content_share
from subscriptions sub
join subscribers using (subscriber_id)
where status = 'cancelled'
group by market;   -- narrow ~0.39, rest ~0.16

-- …and price is a larger share of churn on the entry Basic tier.
select (plan = 'Basic') as is_basic,
       avg((cancel_reason = 'price')::int) as price_share
from subscriptions
where status = 'cancelled'
group by is_basic;   -- Basic ~0.44, others ~0.28
```
