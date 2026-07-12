# Low review ratings foreshadow attrition — but the score is buried in the write-up

- **Signal:** employees who later leave the firm were rated **materially lower** in
  their performance reviews than those who stay — a flight-risk gradient you can read
  off the review history *before* anyone resigns. The catch: each review's 1-5 score is
  not a clean column a student is handed; it is written into the reviewer's free-form
  **narrative**, so the score (and the softer "disengaged / flight risk" tone that often
  rides alongside it) has to be *parsed out of prose* before the leaver-vs-stayer gap can
  be computed. The headline mean rating (~3.6) hides that the low tail concentrates on
  the people on their way out.
- **Documents:** `performance_reviews.narrative` — a free-form text column added to each
  existing review row · doc type **note** (a half-year reviewer write-up) · rough count
  ≈ **one narrative per review row** (`performance_reviews` is already
  `ctx.n`-driven — one row per employee × in-window half-year cycle, floored at 1).
- **Parse target:** the integer **rating (1-5)** rendered in the narrative prose, plus
  (optionally) the departure-risk sentiment. The score appears in 2-3 varied phrasings so
  the parser must handle real variation, e.g.:

  > *"H2 2023 review — Marcus Bell (Senior Associate, Cloud & Infrastructure), reviewed
  > by Dana Wu. Overall performance **rated 2 out of 5** this cycle. Delivery has slipped
  > against plan and engagement has visibly cooled — Marcus has flagged workload twice and
  > reads as disengaged from the practice. Not recommended for promotion."*

  > *"Mid-year 2024 check-in for Priya Nair (Manager, Strategy & Advisory). **Scored a 4**
  > this half — strong client outcomes on Beacon; a dependable performer we should retain."*

  > *"Performance summary | Cycle 2022-H2 | **Rating: 3/5** | Steady, meets-the-bar
  > contributions with room to grow."*

  Extracted field per document: `rating` (and the FK `employee_id` + `cycle` the row
  already carries).
- **Ground truth:** *reconciled against `performance_reviews.rating`* — the existing 1-5
  column the narrative merely renders into prose. The `rating` column is the test's oracle
  (withheld from the student, who is handed only `review_id` / `employee_id` / `cycle` /
  `narrative`); **no answer is leaked** into the text beyond the rating the student is meant
  to extract, and **no answer-key column is added**. The flight-risk slice key is the
  existing `employees.termination_date` (leaver iff non-null).
- **Tables:** `performance_reviews.narrative` (parse source), `performance_reviews.rating`
  (reconcile target), `employees.termination_date` (leaver vs. stayer),
  `employees.hire_date` (tenure, for the sharper trajectory cut) — join
  `performance_reviews` → `employees` on `employee_id`.
- **Magnitude (TO BE PLANTED — target for `/scenario:realize-document`):** leavers'
  mean parsed rating ≈ **3.1** vs stayers ≈ **3.7** — a **~0.5-0.6 point** gap — while the
  overall mean rating stays ≈ **3.6** (the ~18% leaver share blends back to the current
  headline, exactly as the fixed-fee realization plant preserves its ~0.85 marginal). Every
  rating stays an integer in `[1, 5]`. Sharper optional cut once planted: the **final review
  before departure is the lowest** (a declining trajectory into exit), so a leaver's last
  narrative reads more negative than their earlier ones.

Performance ratings today are drawn **independently of attrition** — see the
"Review-rating skew … drawn independently of attrition … the 'low ratings precede
termination' cut is a future scenario" line in `realism-guidance.md`. This scenario is
that future cut, delivered as a *document* problem rather than a clean-column one: the
teaching point is that a folder of review write-ups looks like uniform HR prose, but once
you extract the score from each narrative and join it to who later left, a predictive
flight-risk signal falls out. It is the attrition counterpart to the collection's other
slice stories (`scenarios/no-show-rate.md`, `scenarios/overtime-right-skew.md`) — a flat
top-line (~3.6 average) that decomposes sharply once you control for the right dimension —
and the first labor scenario to make **parsing prose** the analytical bottleneck.

**Current state:** *proposed, not yet realized.* This doc is docs-only; the generator is
unchanged, so (a) the `performance_reviews.narrative` column does not exist yet and (b)
ratings are still drawn on the `reviews` child stream independently of
`employees.termination_date`. Realizing it (`/scenario:realize-document
labor/low-ratings-precede-attrition`) has two parts, both deterministic:
1. **Plant the tilt.** Key the rating draw's *mean* off whether the employee has a
   `termination_date` (lower for leavers, ~3.1 vs ~3.7), keeping the ~18%/82% blend at the
   current ~3.6 marginal — the same "shift the per-row `loc`, not the draw count" move used
   in `project_members.py` for the fixed-fee realization plant, so determinism and the
   `rating ∈ [1, 5]` invariant both hold. (`build_performance_reviews` already reads
   `employees.termination_date`, so no new dependency.)
2. **Render, don't re-sample.** Emit `narrative` by formatting the *already-drawn* `rating`
   into one of 2-3 template phrasings chosen off a name-keyed `ctx.rng.child(...)` stream —
   never draw the rating twice (that would desync the prose from the `rating` column). Until
   then the `realism-guidance.md` "future scenario" bullet stays accurate and is left
   untouched.

## How to find it

```python
# (1) EXTRACTION — parse the 1-5 rating out of each free-form narrative.
# Handles the phrasing variants ("rated N out of 5", "scored a N", "Rating: N/5").
import re
RATING_RE = re.compile(r"(?:rated|scored a|rating:?)\s*(\d)\s*(?:out of 5|/\s*5)?", re.I)

def parse_rating(narrative: str) -> int:
    m = RATING_RE.search(narrative)
    return int(m.group(1))          # 1..5

# LAYER (a) recoverability: parsed rating must equal the withheld ground-truth column.
#   assert parse_rating(row.narrative) == row.rating   # for every performance_reviews row
```

```sql
-- (2) AGGREGATION — leavers were rated lower than stayers (on the PARSED score, but it
-- equals performance_reviews.rating by layer (a) above). termination_date is null for
-- staff still at the firm.
select (e.termination_date is not null)          as left_firm,
       count(*)                                  as reviews,
       round(avg(pr.rating), 2)                  as mean_rating   -- leavers ≈ 3.1, stayers ≈ 3.7
from performance_reviews pr
join employees e using (employee_id)
group by left_firm
order by mean_rating;                            -- leavers row on top (lower)

-- overall mean is preserved (~3.6), hiding the split above
select round(avg(rating), 2) as overall_mean_rating   -- ≈ 3.6
from performance_reviews;

-- sharper (once planted): a leaver's LAST review before exit is their lowest — order a
-- leaver's cycles and the final one reads lowest (a declining trajectory into departure).
```
