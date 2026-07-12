# A whale minority of subscribers drives most premium rentals

- **Signal:** one-off premium (PVOD) rentals are not spread evenly across the base —
  a small "whale" minority of subscribers accounts for a disproportionate share of
  rental transactions (and therefore rental revenue), while most subscribers never
  rent at all.
- **Tables:** `rentals.subscriber_id`, `rentals.price`, `subscribers.subscriber_id`
- **Magnitude:** the top ≈10% of *renting* subscribers place ≈ **45%** of all rentals
  (≈ 0.38–0.45 across seeds; a uniform draw sits near ≈ 0.21), the heaviest renter buys
  ≈ **30+** titles while the typical (median) renter buys **1**, and only ≈ **30%** of
  subscribers ever rent — so most never rent at all. Measured at seed 7 / scale 0.5:
  top-decile-of-renters share ≈ 0.45, heaviest ≈ 33, penetration ≈ 0.30.

The renter of each rental is drawn with a per-subscriber heavy-tailed lognormal propensity
(`renter_weights = exp(N(0, σ)), σ ≈ 1.7`, then a weighted pick over subscriber indices in
`_RENTER_PROPENSITY_SIGMA` / `tables/rentals.py`), replacing the old uniform
`ctx.dist.integers` draw. The weights and the skewed pick run on a dedicated
`child("whale")` stream, so they don't reorder the base-stream title roll — every other
rental field (price, date, payment, rating) stays identical. This turns the PVOD stream
Pareto-like: a whale minority dominates rental volume. The teaching point is that
**transactional revenue is concentrated** — averaging rentals across the whole base ("mean
rentals per subscriber") hides that a handful of accounts carry the stream, so this is a
concentration / Pareto / "mind the whale" exercise and a deliberate foil to the uniform,
one-per-account subscription MRR. It respects every invariant: the renter stays a valid
subscriber, and each rental still resolves to a premium title licensed in that subscriber's
region.

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
  sum(rentals) filter (where decile = 1) * 1.0 / sum(rentals) as top10pct_share,  -- ~0.45 (uniform ~0.21)
  max(rentals)                                                as heaviest_renter,  -- ~30+ (uniform ~5)
  avg(rentals)                                               as mean_per_renter
from ranked;

-- Penetration: most subscribers never rent, so the base is thin and the tail is heavy.
select count(distinct r.subscriber_id) * 1.0 / (select count(*) from subscribers)
         as renter_penetration            -- ~0.30 ever rent (seed 7 / scale 0.5)
from rentals r;
```
