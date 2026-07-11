# Rising claim counts are exposure growth, not a deteriorating book

- **Signal:** raw claim volume climbs steeply year over year, but that rise is
  **pure exposure growth** — the book fills from zero at the window's `start_date`,
  so more policies are in force each year. Normalize by the in-force count (or by
  exposed policy-years) and per-policy claim *frequency* is **flat** across all three
  years. The naive "claims are up ~80%, the book is deteriorating" read inverts.
- **Tables:** `claims.claim_date`, `claims.policy_id`, `policies.start_date`,
  `policies.term_months` (count claims per calendar year, then divide by the in-force
  policies that year).
- **Magnitude:** raw claims per calendar year ≈ **132 → 217 → 237** (2022→2024, a
  **~1.8×** rise), but in-force policies rise in lock-step ≈ **1,650 → 3,080 → 3,110**
  (**~1.9×**), so claims-per-in-force is **flat ≈ 0.07–0.08** every year (and the
  exposure-year–normalized annual frequency is flat ≈ **0.16**, the blended tier λ).
  (Counts are `seed=7, scale=1.0`. At the scenario test's `seed=7, scale=0.5` the same
  shape holds at half the volume: raw **64 → 119 → 112** (last/first **~1.75×**), in-force
  **818 → 1,510 → 1,552**, claims-per-in-force flat **≈ 0.072–0.079** (max/min **~1.09**);
  small-n and noisy below full scale.)

Claim counts are a per-policy `Poisson(λ × exposed_years)` where `exposed_years` is the
policy term **clipped to the run window**, and the book is a **cold-start** one — no
backdated policies, so the in-force grows from zero at `start_date`. That makes total
claim volume ramp ~2× across the three years even though nothing about per-policy risk
changes. The teaching point is the exposure-vs-frequency trap: a rising *count* is not a
rising *rate*. Before calling a trend, divide by the exposure that produced it
(in-force policies, or exposed policy-years) — here the trend evaporates, and the
"deterioration" was just a growing book. (This promotes the **Cold-start book**
simplification in `realism-guidance.md` into an explicit teachable signal; it pairs with
the companion fact that there is *no* claim pile-up at the window end — per-policy
frequency is flat in time as well as across years.)

## How to find it

```sql
-- 1) raw claim counts ramp ~1.8x across the window (looks like a worsening book)
select year(claim_date) as yr, count(*) as claims
from claims group by yr order by yr;                 -- ≈ 132, 217, 237  (2022→2024)

-- 2) but in-force policies ramp in lock-step, so normalize by them
with inforce as (
  select y.yr,
         count(*) filter (
           where p.start_date <= make_date(y.yr, 12, 31)
             and (p.start_date + to_days((p.term_months * 30.4)::int)) >= make_date(y.yr, 1, 1)
         ) as in_force
  from (select unnest([2022, 2023, 2024]) as yr) y
  cross join policies p
  group by y.yr
),
cl as (select year(claim_date) as yr, count(*) as claims from claims group by yr)
select inforce.yr, cl.claims, inforce.in_force,
       cl.claims::float / inforce.in_force as claims_per_inforce  -- ≈ 0.080, 0.070, 0.076 (FLAT)
from inforce join cl using (yr)
order by inforce.yr;
-- raw claims ≈ +80%, in-force ≈ +89%, per-policy frequency ≈ flat: the rise is exposure, not risk.
```
