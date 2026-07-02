# Premium-eligible titles score higher than the back catalogue

- **Signal:** titles flagged `is_premium` (rental-eligible new/day-and-date
  releases) carry a higher `avg_rating` than the rest of the catalogue.
- **Tables:** `titles.is_premium`, `titles.avg_rating`
- **Magnitude:** mean `avg_rating` ≈ 7.5 for premium titles vs ≈6.3 for
  non-premium, on a 1–10 scale (a ~1.2-point lift).

`avg_rating` is a per-title quality score whose mean is keyed on `is_premium`, so
the rental-eligible slice skews toward the top of the scale. The teaching point is
a clean two-group comparison — premium content is both monetised separately (the
rentals stream) *and* rated higher — and a caution against reading `avg_rating`
flat across the catalogue. Note this contrasts with the rental *transaction*
signal (`premium-rentals-rate-lower.md`), where the priciest rental **tier** rates
worst: the catalogue-quality score and the per-rental satisfaction are different
measures.

## How to find it

```sql
-- premium-eligible titles rate about a point higher on the catalogue-quality score.
select is_premium,
       avg(avg_rating) as mean_rating  -- premium ~7.5, non-premium ~6.3
from titles
group by is_premium;
```
