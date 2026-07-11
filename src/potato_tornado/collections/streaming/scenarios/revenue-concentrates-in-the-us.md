# The US pays a premium — revenue is flat everywhere else

- **Signal:** the US generates a bigger slice of monthly revenue than its share of
  subscribers, and its average revenue per subscriber (ARPU) sits well above every
  other market — while the five non-US markets are nearly indistinguishable from
  one another on ARPU. List prices are identical across markets, so the gap is pure
  tier mix, not local pricing.
- **Tables:** `subscriptions.mrr`, `subscriptions.plan`, `subscribers.region`
  (join on `subscriber_id`)
- **Magnitude:** US ≈ **41%** of total MRR from only ≈ **35%** of subscribers; US
  ARPU ≈ **$15.6** vs ≈ **$12.2** for the rest — and the non-US markets bunch in a
  tight ~$11.9–$12.6 band (BR/IN/GB/JP/DE), so the US is a lone outlier, not the top
  of a gradient. (~27% ARPU premium; robust across seeds/scales.)

`mrr` is a pure derivation off the plan price and billing cadence, and plan prices
carry **no per-market adjustment** (a deliberate no-local-pricing simplification —
everyone pays the same USD list price). So the entire ARPU spread comes from *what
subscribers buy*, not what they're charged: the US skews to Premium
(`standard-is-the-most-popular-plan.md`), so its ARPU lifts, while every other
region shares the same Standard-heavy plan weights and therefore lands on the same
~$12 ARPU. The teaching point is that **revenue share ≠ headcount share** — a third
of the base carries ~40% of MRR — and that ARPU alone can't distinguish the five
non-US markets (you'd need volume, not price, to rank them). It reframes the plan
mix as a revenue-prioritisation question the plan-count scenario doesn't answer.

## How to find it

```sql
-- US punches above its headcount on revenue; ARPU is flat across the other markets.
select s.region,
       count(*)                                     as subs,
       count(*) * 1.0 / sum(count(*)) over ()       as sub_share,   -- US ~0.35
       sum(sub.mrr)                                 as mrr,
       sum(sub.mrr) / sum(sum(sub.mrr)) over ()     as rev_share,   -- US ~0.41
       sum(sub.mrr) / count(*)                      as arpu         -- US ~15.6, rest ~12.0-12.6
from subscriptions sub
join subscribers s using (subscriber_id)
group by s.region
order by arpu desc;   -- US alone on top; BR/IN/GB/JP/DE cluster near $12
```
