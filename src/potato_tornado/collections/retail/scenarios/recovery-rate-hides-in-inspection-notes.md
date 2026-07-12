# Resale-recovery runs against the return-rate gradient — and it lives in the inspection notes

- **Signal:** how much of a return is *recovered* (goes back to sellable stock) does
  **not** track how often a category is returned. Apparel — the **highest-return**
  category (≈ 0.22) — has the **highest** resale-recovery rate (≈ 0.68 of its returns
  restock), because its returns are fit / changed-mind and arrive resellable. Electronics —
  returned far less often (≈ 0.10) — has the **lowest** recovery (≈ 0.45), because its
  returns are defect / damage and arrive unsellable. So "where do returns hurt?" flips from
  *volume* (apparel) to *unrecoverable value* (electronics). The recovery decision is
  captured only as free-text in a warehouse **inspection note**, so the pattern is invisible
  until the notes are parsed and aggregated by category.
- **Documents:** `returns.inspection_note` *(text column to be added on `returns` at the
  realize step)* — a free-form returns-processing / warehouse inspection note, exactly one
  per return (a return naturally has one inspection), so it's a column on the existing table,
  not a new table. Row count rides `returns` (≈ 1.7k at `scale=0.5`, ≈ 3.5k at `scale=1.0`).
  Doc type: **note**.
- **Parse target:** from each note, extract (1) the **disposition** — "returned to sellable
  stock" vs "routed to disposal / quarantined / not resellable" → a `restocked` boolean — and
  (2) the corroborating **arrival-condition** phrase ("tags attached, unworn" / "box opened,
  contents unused" / "screen cracked, will not power on") → `{resellable, opened, damaged}`.
  Example note:

  > *Received RET-0004521 and inspected — earbuds arrive with a cracked case and won't pair;
  > not resellable, routed to disposal.*

  → `item_condition = damaged`, `restocked = False`. The note never states the product
  category or any rate — those are recovered by joining and aggregating, not by reading.
- **Ground truth:** reconciled against the **existing structured columns**
  `returns.item_condition` and `returns.restocked` — the note merely *renders* the values
  those columns already hold (derived, never re-sampled). No answer-key column is shipped and
  nothing is leaked into the prose: category comes from the
  `returns.order_item_id → order_items.product_id → products.category` join, and the recovery
  rate from the aggregation. (What makes this a *document* scenario, not a plain
  `SELECT restocked`: the recovery decision is authentically an unstructured inspection note,
  and the never-before-documented category **inversion** only appears after the notes are
  parsed into a boolean and rolled up — the reconciliation columns are the test's oracle, not
  the analyst's input.)
- **Tables:** `returns.inspection_note` (parsed) reconciled to `returns.item_condition` /
  `returns.restocked`; joined via `order_items.product_id` to `products.category`; read
  alongside the per-category return rate (`order_items ⋈ returns`, see
  `return-rate-by-category.md`).
- **Magnitude — PLANTED (the facts already exist; only the prose rendering is to be added).**
  Per-category resale-recovery (restock) rate, measured at `seed=7, scale=0.5`:
  **apparel ≈ 0.68 / consumables ≈ 0.52 / home ≈ 0.47 / electronics ≈ 0.45** (overall ≈ 0.62)
  — a ranking that does **not** match the return-rate ranking
  (apparel 0.22 / electronics 0.10 / home 0.06 / consumables 0.02). Damaged-on-arrival share
  runs the opposite way to recovery: apparel ≈ 0.19 (lowest) vs electronics ≈ 0.42 (highest),
  home ≈ 0.39, consumables ≈ 0.38. The headline contrast: **apparel returns ≈ 2.3× as often
  as electronics yet recovers ≈ 1.5× the share of each return** — the big-volume return
  category is the *recoverable* one; the smaller electronics stream is the write-off.

An analyst is handed the return inspection notes (free text), not a clean `restocked` flag.
The work is to parse each note into a disposition + condition, join the return to its product
category, then aggregate resale-recovery by category — and discover it runs *against* the
return-rate story the collection already teaches (`return-rate-by-category.md`). The teaching
point mirrors `margin-differs-by-category.md`: a second per-category gradient (recovery) that
crosses the return gradient, so the naive "apparel is the returns problem" reading is
incomplete — apparel's returns are mostly recoverable inventory, while electronics' fewer
returns are mostly destroyed value. It's planted because both the condition and the
disposition are keyed through `reason → item_condition → restocked` (see `returns.py`), and
the note renders those already-computed values, so the signal is legible only after the prose
is read.

## How to find it

```python
# (1) EXTRACTION — parse the free-text note into structured fields, then reconcile against
#     the real columns to prove the signal is recoverable from prose (no leak).
import re, polars as pl

def parse_note(text: str) -> tuple[str, bool]:
    t = text.lower()
    # disposition -> restocked
    restocked = bool(re.search(r"returned to (sellable|resell\w*) stock|back to stock|restock", t)) \
        and not re.search(r"not resell|disposal|quarantin|scrap|write[- ]?off", t)
    # arrival condition -> item_condition
    if re.search(r"crack|shatter|won'?t power|dead|torn|stained|damaged|broken", t):
        cond = "damaged"
    elif re.search(r"box opened|opened|unsealed|worn once|tried on", t):
        cond = "opened"
    else:                                   # "tags attached", "unworn", "sealed", "as new"
        cond = "resellable"
    return cond, restocked

parsed = returns.with_columns(
    pl.col("inspection_note")
      .map_elements(lambda s: parse_note(s), return_dtype=pl.List(pl.Utf8))  # sketch
)
# Layer (a): parsed disposition == returns.restocked, parsed condition == returns.item_condition
#            (deterministic — the note renders those columns; the test asserts equality).

# (2) AGGREGATION — resale-recovery by category, read against return rate. Use the parsed
#     `restocked` (or the reconciled column) joined to the product category.
```

```sql
-- recovery rate by category does NOT track return rate (the inversion)
with lines as (
  select oi.order_item_id, p.category,
         (r.order_item_id is not null) as returned,
         r.restocked
  from order_items oi
  join products p using (product_id)
  left join returns r using (order_item_id)
)
select category,
       avg(returned::int)                               as return_rate,   -- appa .22 elec .10 home .06 cons .02
       avg(restocked::int) filter (where returned)      as recovery_rate  -- appa .68 cons .52 home .47 elec .45
from lines
group by category
order by return_rate desc;
-- highest-return category (apparel) has the HIGHEST recovery; electronics is 2nd in returns
-- but LOWEST recovery — recovery runs against the return gradient, only visible once the
-- disposition is parsed out of `inspection_note` (seed 7, scale 0.5).
```
