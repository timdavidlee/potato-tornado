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
  (optionally) the departure-risk sentiment. The score appears in three varied phrasings
  (chosen off a name-keyed `ctx.rng.child("template")` stream) so the parser must handle
  real variation — these are the exact three layouts the generator emits:

  > *"H2 2023 review — Marcus Bell (Senior Associate, Cloud & Infrastructure), reviewed
  > by Dana Wu. Overall performance **rated 2 out of 5** this cycle. Delivery has slipped
  > against plan and engagement has visibly cooled; reads as disengaged from the practice
  > and is not recommended for promotion this cycle."*

  > *"Mid-year 2024 check-in for Priya Nair (Manager, Strategy & Advisory). **Scored a 4**
  > this half — Strong client outcomes and dependable delivery — a performer we should keep
  > investing in and retain."*

  > *"Performance summary | Cycle 2022-H2 | Senior Associate, Data & Analytics |
  > **Rating: 3/5** | Steady, meets-the-bar contributions this half, with clear room to
  > grow."*

  A single case-insensitive regex covers all three:
  `(?:rated|scored a|rating:?)\s*(\d)\s*(?:out of 5|/\s*5)?`. The departure-risk tone is a
  digit-free function of the *rendered* rating only (low scores read negative, high scores
  read as "retain"), so it never leaks the leaver flag and never confuses the parser.
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
- **Magnitude (planted; measured at seed=7, scale=0.5):** leavers' mean parsed rating
  ≈ **2.85** vs stayers ≈ **3.63** — a **~0.78 point** measured gap — while the overall mean
  rating stays ≈ **3.59** (unchanged from the pre-plant ~3.56). By **design** the tilt sets
  the per-row rating *mean* to **3.1** for leavers and **3.66** for stayers, an expected
  ~**0.5** gap; the measured seed=7 gap runs above that because leavers are only ~**6%** of
  review *rows* (n≈27 at scale=0.5) — they accrue fewer half-year cycles before leaving, so
  the small leaver sample swings, and the ~6%/94% blend is what keeps the ~3.6 headline
  intact (cross-seed the leaver-vs-stayer gap runs ~0.3–0.66). Every rating stays an integer
  in `[1, 5]`, and the score parsed from every narrative equals `performance_reviews.rating`
  (0 mismatches across all three phrasings). The tilt is a **flat** per-leaver mean shift, so
  the sharper "final review before departure is the lowest" declining-trajectory cut is
  **not** planted — a future sharpening.

The teaching point: a folder of review write-ups looks like uniform HR prose, but once you
extract the score from each narrative and join it to who later left, a predictive flight-risk
signal falls out. It is the attrition counterpart to the collection's other slice stories
(`scenarios/no-show-rate.md`, `scenarios/overtime-right-skew.md`) — a flat top-line (~3.6
average) that decomposes sharply once you control for the right dimension — and the first
labor scenario to make **parsing prose** the analytical bottleneck.

**Current state:** *realized* in `tables/performance_reviews.py`. Two deterministic parts,
both in `build_performance_reviews`:
1. **The tilt is planted.** The rating draw's *mean* is keyed off whether the employee has a
   `termination_date` via `_RATING_MEAN_LEAVER` (3.1) / `_RATING_MEAN_STAYER` (3.66) — only
   the per-row `loc` of the same `Normal(mean, 0.9)` draw changes (the draw count is
   unchanged, so determinism holds and the `rating ∈ [1, 5]` clamp is untouched), the same
   move `project_members.py` uses for the fixed-fee realization plant.
2. **The narrative renders, never re-samples.** `narrative` formats the *already-drawn*
   `rating` into one of three phrasings chosen off a name-keyed `ctx.rng.child("template")`
   stream, so the prose reconciles exactly against the `rating` column. `reviewer` /
   department names are incidental filler pulled from `employees` + `departments` (a new
   `depends_on`); the departure-risk tone is a function of the rendered rating only.

The two-layer scenario test lives in `tests/collections/labor/test_scenarios.py`
(`test_review_narrative_rating_is_recoverable`, `test_leavers_are_rated_below_stayers`,
`test_overall_review_rating_mean_is_preserved`).

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
       round(avg(pr.rating), 2)                  as mean_rating   -- leavers ≈ 2.85, stayers ≈ 3.63
from performance_reviews pr
join employees e using (employee_id)
group by left_firm
order by mean_rating;                            -- leavers row on top (lower)

-- overall mean is preserved (~3.6), hiding the split above
select round(avg(rating), 2) as overall_mean_rating   -- ≈ 3.59
from performance_reviews;

-- NOT planted (a future sharpening): a declining trajectory into exit, where a leaver's
-- LAST review before departure is their lowest. Today the tilt is a flat per-leaver mean
-- shift, so a leaver's cycles do not trend down toward their termination date.
```
