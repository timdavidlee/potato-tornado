# Catalogue size varies by region

- **Signal:** the number of licensed titles differs sharply by market — the US
  carries most of the catalogue, Japan the least — following each region's
  licensing density.
- **Tables:** `title_availability.region`, `title_availability.title_id`, `regions.region`
- **Magnitude:** US ≈ 87% of all titles down to Japan ≈ 30% — a ~2.9× gap. The
  density ordering is US > GB > DE > BR > IN > JP (the GB/DE and BR/IN pairs are
  near-ties that can swap under sampling noise).

`title_availability` is a many-to-many licensing bridge: each title is licensed to
a subset of regions, with larger markets licensing a bigger share of the
catalogue. Counting rows per region reproduces the density gradient, and the gap
between the widest and narrowest market is the teaching point — "how much of the
catalogue can I actually watch here?".

## How to find it

```sql
select r.region,
       count(*)                                             as titles_available,
       count(*) * 1.0 / (select count(*) from titles)       as catalogue_share
from title_availability ta
join regions r using (region)
group by r.region
order by titles_available desc;          -- US ≈ 0.85+ ... JP ≈ 0.30
```
