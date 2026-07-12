# Cancellation notes reveal price-shopping: flexible rates cancel to chase a cheaper deal

- **Signal:** the *reason* a booking cancelled — recorded only in the free-form
  guest-service note, nowhere in a column — is not uniform across rate plans. Flexible
  **BAR** cancellations overwhelmingly cite **price/rate-shopping** ("found a cheaper rate",
  "rate dropped elsewhere"), while non-refundable **Advance-Purchase** cancellations cite a
  **genuine plan change** ("trip cancelled", "family emergency"). The reason tracks the rate
  plan — and therefore the late-vs-early cancel *timing* already documented in
  `cancellations-land-late-for-flexible-rates.md`: price-driven churn concentrates in the
  refundable rates a guest can walk away from for free, and it lands late in the window.
- **Documents:** `cancellation_notes.body` — a new table, **one row per cancelled
  reservation** (`ctx.n(24000)` bookings × ≈11.5% cancelled ≈ **2,760** notes at full scale,
  ≈1,385 at `scale=0.5`; floor of 1) · doc type = **free-form note** (front-desk /
  guest-service cancellation log entry).
- **Parse target:** two fields per note — (a) the **days before arrival** the guest cancelled
  ("phoned 5 days before arrival"), and (b) the **reason phrase**, bucketed to
  `{rate_shopping, plans_changed, other}`. Example body:

  > *"Guest phoned 5 days before arrival to cancel **RES-0001234** — said they'd found a
  > cheaper flexible rate at a property down the street. Refunded in full per BAR terms."*

  pulls `days_before = 5`, `reservation_id = RES-0001234`, `reason = rate_shopping`.
- **Ground truth:** split — no leak on the timing, a withheld key on the reason.
  - **Timing** reconciles against existing columns: parsed `days_before` must equal
    `reservations.check_in_date − reservations.cancellation_date` for that reservation, so the
    prose is a faithful render of the real dates (no answer leaked).
  - **Reason** exists nowhere else in the schema, so it ships as a **withheld** answer-key
    column `cancellation_notes.cancel_reason` beside `body` — held back when the notes are
    handed to students; the test parses the reason from `body` and reconciles it against this
    column, then aggregates by `rate_plan`.
- **Tables:** `cancellation_notes.body`, `cancellation_notes.reservation_id` (FK),
  `cancellation_notes.cancel_reason` (**withheld**), `reservations.rate_plan`,
  `reservations.status`, `reservations.cancellation_date`, `reservations.check_in_date`.
- **Magnitude — planted.** The reason is drawn conditional on `rate_plan` in
  `build_cancellation_notes` (`_REASON_WEIGHTS_BY_PLAN`). Measured at `scale=0.5`, seed 21
  (the scenario-test fixture): **1,470 notes** (BAR 826 / Package 272 / Advance-Purchase 195
  / Corporate-negotiated 177):
  - Among **BAR** cancellations: `rate_shopping` ≈ **0.63** (the dominant reason);
    `plans_changed` ≈ 0.20; `other` ≈ 0.16.
  - Among **Advance-Purchase** cancellations: `plans_changed` ≈ **0.67** (dominant),
    `rate_shopping` ≈ **0.17** (≤ 0.20) — the mirror image. Package (`rate_shopping` ≈ 0.46)
    and Corporate-negotiated (`plans_changed` ≈ 0.54) sit between.
  - Overall reason split ≈ `rate_shopping 0.50 / plans_changed 0.34 / other 0.16` — an emergent
    product of the rate-plan mix among cancellations (BAR is ≈56% of them, so its
    rate_shopping tilt dominates the pooled total).
  - The **timing** half is already true today and needs no planting: BAR cancels ≈**11** days
    out (window fraction ≈0.62), Advance-Purchase ≈**23** days out (≈0.23).

`status = 'cancelled'` and `cancellation_date` already tell you *that* and *when* a booking
cancelled, but never *why* — hotels record the reason as a free-text note, not a coded field.
An analyst asking "are we losing refundable bookings to price competition?" cannot answer it
with a `GROUP BY`: they must read the notes, bucket each into a reason, join back to the
reservation's rate plan, and only then see that price-shopping is a **refundable-rate**
phenomenon (you shop and bail when you can leave for free) while non-refundable cancellations
are the genuine, unavoidable kind. That is the teaching point — the reason is legible only
after parsing, and it explains *why* the flexible rates both cancel more and cancel late. It
promotes the collection's unmodelled guest-notes text into its first parse-the-prose signal,
adjacent to but distinct from the two existing cancellation scenarios (which cover cancel
*rate* and cancel *timing* by rate plan, never the reason).

## How to find it

```python
# 1) EXTRACTION — parse each note body into (reservation_id, days_before, reason).
import re
import polars as pl

RATE_WORDS = ("cheaper rate", "better rate", "lower rate", "rate dropped", "price", "deal")
PLAN_WORDS = ("trip cancelled", "plans changed", "rescheduled", "emergency", "flight",
              "no longer travel", "postponed")

def bucket(body: str) -> str:
    low = body.lower()
    if any(w in low for w in RATE_WORDS):
        return "rate_shopping"
    if any(w in low for w in PLAN_WORDS):
        return "plans_changed"
    return "other"

notes = frames["cancellation_notes"]
parsed = notes.with_columns(
    res_id=pl.col("body").str.extract(r"(RES-\d{7})"),
    days_before=pl.col("body").str.extract(r"(\d+)\s+days?\s+before\s+arrival", 1).cast(pl.Int64),
    reason=pl.col("body").map_elements(bucket, return_dtype=pl.Utf8),
)

# Round-trip checks (prove the prose renders the ground truth, no leak):
#   parsed.days_before == check_in_date - cancellation_date   (reconcile vs. reservations)
#   parsed.reason      == cancellation_notes.cancel_reason    (reconcile vs. withheld key)

# 2) AGGREGATION — reason share by rate plan (join notes -> reservations on reservation_id).
res = frames["reservations"].select("reservation_id", "rate_plan")
mix = (
    parsed.join(res, left_on="res_id", right_on="reservation_id")
    .group_by("rate_plan", "reason").len()
    .with_columns(share=pl.col("len") / pl.col("len").sum().over("rate_plan"))
    .sort("rate_plan", "reason")
)
# expected (measured, scale=0.5 seed 21):
#   BAR              -> rate_shopping ~0.63   (dominant)
#   Advance-Purchase -> plans_changed ~0.67   (dominant), rate_shopping ~0.17 (<= 0.20)
```

```sql
-- SQL sketch once the reason is parsed out into a temp column `reason`:
-- price-shopping is a refundable-rate phenomenon.
select r.rate_plan,
       avg((n.reason = 'rate_shopping')::int) as rate_shopping_share
from cancellation_notes n
join reservations r using (reservation_id)
group by r.rate_plan
order by rate_shopping_share desc;   -- BAR on top (~0.6-0.7), Advance-Purchase at the bottom (<=0.2)
```
