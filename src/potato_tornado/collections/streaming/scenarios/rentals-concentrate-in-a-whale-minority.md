# A whale minority of subscribers drives most premium rentals

- **Signal:** one-off premium (PVOD) rentals are not spread evenly across the base —
  a small "whale" minority of subscribers accounts for a disproportionate share of
  rental transactions (and therefore rental revenue), while most subscribers never
  rent at all.
- **Tables:** `rentals.subscriber_id`, `rentals.price`, `subscribers.subscriber_id`
- **Magnitude:** *target — to be planted.* Aim for the top ≈10% of *renting*
  subscribers to place ≈45% of all rentals, with the heaviest renters buying
  15–30+ titles while the typical renter buys 1. **This signal is NOT present
  today:** the renter of each rental is drawn uniformly, so the spread is flat
  (top-decile renters carry only ≈0.21 of rentals, and no subscriber rents more
  than ~5 at `scale=1.0`). Needs planting.

The renter of each rental is currently a uniform draw
(`sub_idx = ctx.dist.integers(n, 0, num_subs - 1)` in `tables/rentals.py`), so
rentals-per-subscriber is a flat, Poisson-ish spread with no heavy tail —
`realism-guidance.md` records this as a deliberate simplification ("Rentals spread
uniformly across subscribers … no heavy-renter concentration") and names whale
concentration as a candidate future scenario. Planting a heavy-tailed renter draw
(a skewed / power-law pick over subscribers) turns the PVOD stream Pareto-like: a
whale minority dominates rental volume. The teaching point is that **transactional
revenue is concentrated** — averaging rentals across the whole base ("mean rentals
per subscriber") hides that a handful of accounts carry the stream, so this is a
concentration / Pareto / "mind the whale" exercise and a deliberate foil to the
uniform, one-per-account subscription MRR. It respects every invariant: the renter
stays a valid subscriber, and each rental still resolves to a premium title
licensed in that subscriber's region.

## How to find it

```sql
-- Rank renters by volume, then measure the top decile's share of all rentals.
with per_renter as (
  select subscriber_id,
         count(*)   as rentals,
         sum(price) as rental_revenue
  from rentals
  group by subscriber_id
),
ranked as (
  select *, ntile(10) over (order by rentals desc) as decile
  from per_renter
)
select
  sum(rentals) filter (where decile = 1) * 1.0 / sum(rentals) as top10pct_share,  -- target ~0.45 (today ~0.21)
  max(rentals)                                                as heaviest_renter,  -- target 15-30+ (today ~5)
  avg(rentals)                                               as mean_per_renter
from ranked;

-- Penetration: most subscribers never rent, so the base is thin and the tail is heavy.
select count(distinct r.subscriber_id) * 1.0 / (select count(*) from subscribers)
         as renter_penetration            -- a minority of accounts ever rent
from rentals r;
```
