# Standard leads overall, but Premium is the US's plan of choice

- **Signal:** subscribers pick the mid-tier `Standard` plan about half the time
  overall — but that blend hides a regional split. **The US skews upmarket:
  Premium is the modal plan there**, while every other region leans toward
  Standard even more heavily than the global average.
- **Tables:** `subscriptions.plan`, `subscribers.region` (join on `subscriber_id`)
- **Magnitude:** overall Standard ≈ 46%, Basic ≈ 28%, Premium ≈ 26%. Within the US,
  Premium ≈ **53%** (modal) vs Standard ≈ 29% and Basic ≈ 18%. Outside the US,
  Standard ≈ 55%, Basic ≈ 34%, Premium ≈ 11%.

The plan mix is the collection's core subscription signal, and a flat "Standard
wins" reading misses that the US market behaves completely differently: split by
`region` and Premium overtakes Standard for US subscribers specifically. It's the
setup for a market-prioritisation question — which region should a Premium-tier
marketing push target? — and turns the plan mix into a segmentation exercise
rather than a single global fact.

## How to find it

```sql
-- overall: Standard leads
select plan, count(*) * 1.0 / sum(count(*)) over () as share
from subscriptions
group by plan order by share desc;                 -- Standard ~0.46

-- but the US flips to Premium
select s.region, sub.plan, count(*) as subs
from subscriptions sub
join subscribers s using (subscriber_id)
group by s.region, sub.plan
order by s.region, subs desc;                       -- US -> Premium on top
```
