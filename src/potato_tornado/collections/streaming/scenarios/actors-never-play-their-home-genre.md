# Every title is off-brand for its lead actor

- **Signal:** joining `titles` to `actors` on the lead actor, no title's `genre`
  ever equals that actor's `home_genre` — the whole catalogue is a genre mismatch.
  The visible payoff: comedy-native figures (Kevin Hart, Jerry Seinfeld) never
  headline a `comedy` title, even though `comedy` is a perfectly valid show genre
  that other figures do get.
- **Tables:** `titles.lead_actor`, `titles.genre`, `actors.actor`, `actors.home_genre`
- **Magnitude:** exactly 0 titles match their actor's home genre; the mismatch is 100%.

This is the collection's headline gag made queryable. `titles.genre` is drawn from
a valid show genre that deliberately excludes the actor's `home_genre`, so the
join is the "answer key": every matched row is off-brand. It's a natural setup for
an anti-join / referential question, and for spotting that a genre available to the
roster at large is systematically withheld from the figures who own it.

## How to find it

```sql
-- No title sits in its lead actor's home genre.
select count(*)
from titles t
join actors a on t.lead_actor = a.actor
where t.genre = a.home_genre;              -- 0

-- Comedy-native figures appear, but never in a comedy title.
select a.actor,
       count(*)                              as titles,
       count(*) filter (where t.genre = 'comedy') as comedy_titles
from titles t
join actors a on t.lead_actor = a.actor
where a.home_genre = 'comedy'
group by a.actor;                          -- comedy_titles = 0 for every row
```
