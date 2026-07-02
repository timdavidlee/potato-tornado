# Guests who check out early leave lower review scores

- **Signal:** the post-stay `review_score` (1-5) is high overall (~4.1 mean, left-skewed
  toward 4s and 5s), but stays that ended in an **early checkout score about a full point
  lower** — ~3.1 vs ~4.1 for stays that ran as booked — while extensions score a touch higher
  (~4.4). Secondarily, the **OTA** channel runs below the loyalty-heavy **direct** channel
  (~3.9 vs ~4.3).
- **Tables:** `stays.review_score`, `stay_changes.change_type` (join on `stay_id`),
  `reservations.channel` (join on `reservation_id`)
- **Magnitude:** mean score by outcome — early_checkout ≈3.1 ≪ none ≈4.1 < extension ≈4.4.
  By channel: direct ≈4.3 > corporate ≈4.2 > walk_in ≈4.1 > ota ≈3.9.

`review_score` is the collection's outcome variable — the thing every other dimension is
ultimately trying to predict. The planted link is the intuitive one: a guest who cut their
stay short was unhappy, and the score reflects it. It's the natural setup for a
driver-analysis question ("what predicts a bad review?") whose answer is *the early checkout*,
not the room class or the property. Because the dip keys off the same stay-length amendment
that `stay_changes` records (`scenarios/extensions-outnumber-early-checkouts.md`), the two
tables reconcile: the early-checkout rows in `stay_changes` are exactly the low-scoring stays.

## How to find it

```sql
-- score by stay outcome: early checkouts score ~1 point lower
select coalesce(c.change_type, 'none') as outcome,
       avg(s.review_score) as mean_score, count(*) as stays
from stays s
left join stay_changes c using (stay_id)
group by outcome order by mean_score;    -- early_checkout ≈3.1, none ≈4.1, extension ≈4.4

-- secondary: OTA stays score below direct
select r.channel, avg(s.review_score) as mean_score
from stays s join reservations r using (reservation_id)
group by r.channel order by mean_score;  -- ota ≈3.9 at the bottom, direct ≈4.3 on top
```
