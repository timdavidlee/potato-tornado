# The priciest rental tier rates the worst

- **Signal:** among rentals that leave a rating, the rare $19.99 day-and-date tier
  scores markedly lower than the two cheaper catalogue tiers — a
  price-expectation / buyer's-remorse gap.
- **Tables:** `rentals.price`, `rentals.rating`
- **Magnitude:** mean `rating` ≈ 4.0 at $4.99 and $6.99, but ≈2.8 at $19.99 (on a
  1–5 scale). Only ~40% of rentals carry a rating (the rest are null).

`rating` is nullable — most rentals aren't rated — and the score mean is keyed on
the price point, with the $19.99 day-and-date release drawing a lower mean than
the $4.99/$6.99 catalogue rentals. It builds on the skewed PVOD price ladder
(`test_rental_price_mix_is_skewed_toward_cheaper_tiers`): the tier that is both
rarest *and* most expensive is also the least satisfying, so paying more buys
worse-received content — a margin-vs-satisfaction discussion. Because ratings are
sparse, it's also a "mind the nulls" exercise: average only over rated rows.

## How to find it

```sql
-- mean rating by price tier, over rated rentals only.
select price,
       avg(rating) as mean_rating,  -- 4.99 ~4.0, 6.99 ~4.0, 19.99 ~2.8
       count(rating) as rated
from rentals
where rating is not null
group by price
order by price;
```
