# Gradual water-damage losses settle far below sudden ones — and the cause is only in the note

- **Signal:** among `water_damage` claims, the ones an adjuster describes as **gradual**
  (long-term seepage / wear, a coverage-excluded cause) settle at a **much lower**
  paid-to-reported ratio than the ones described as a **sudden accidental discharge**
  (a burst pipe — a covered cause): gradual losses are denied or partialed far more
  often. The structured `peril` column shows one blended `water_damage` bucket; the
  sudden-vs-gradual split that drives the payout gap exists **only in the free-text
  loss description**, so a plain `GROUP BY peril` cannot see it — you have to read the
  note.
- **Documents:** `adjuster_notes.body` — a free-form adjuster **loss-description note**,
  one per claim (`ctx.n(...)` ≈ claim count: ~295 at `scale=0.5`, ~586 at `scale=1.0`;
  ~22% are `water_damage`). The note narrates the loss cause and renders the reported
  loss estimate in prose.
- **Parse target:** for each note, (a) the loss estimate dollar figure and (b) — for
  water losses — a **sudden vs gradual** classification from the wording. Keyword cues:
  *gradual* → "seepage", "long-term", "gradual", "wear", "deterioration", "over time",
  "maintenance"; *sudden* → "burst", "sudden", "accidental discharge", "ruptured",
  "sprang a leak". Example (gradual):

  > Inspected POL-0001234 on 2023-06-14. Damage traced to **long-term seepage** behind
  > the shower wall — consistent with **gradual** deterioration, not a single event.
  > Initial loss estimate **$7,900**. Coverage position under review given the
  > wear-and-tear exclusion.

  Example (sudden):

  > FNOL for POL-0004567: a supply line under the kitchen sink **burst** on 2023-06-14,
  > **sudden discharge** flooding the cabinets. Initial loss estimate **$6,300**. Clear
  > accidental-discharge trigger.

  Extract `loss_estimate = 7900` and `cause = gradual` from the first; `6300` / `sudden`
  from the second.
- **Ground truth:** the payout side already lives in structured columns — the parsed
  `loss_estimate` reconciles against `claims.reported_amount`, and the paid-to-reported
  ratio is computed from the real `claim_payments.paid_amount` / `claims.status`, **no
  answer leaked**. The one fact with no home elsewhere is the sudden/gradual label; it is
  shipped as a **withheld** `adjuster_notes.water_cause` answer-key column (`sudden` /
  `gradual` / null for non-water claims) used **only** to check the parser round-trips —
  it is **not** handed to students, who must recover the label from `body`.
- **Tables:** `adjuster_notes.body`, `adjuster_notes.claim_id`,
  `adjuster_notes.water_cause` (withheld key), `claims.peril`, `claims.reported_amount`,
  `claims.status`, `claim_payments.paid_amount`.
- **Magnitude (to be planted):** today water-damage claims settle at the **book average**
  (paid-to-reported ≈ **0.63**, `seed=7`) because adjudication is cause-independent — the
  split does not exist yet. Target once planted: split water losses **sudden ≈ 0.60 /
  gradual ≈ 0.40**; gradual carries an elevated denied+partial share (≈ **0.45 denied /
  0.25 partial**, so only ~1-in-4 pays in full) vs. sudden at the book mix (approved ≈
  0.62). That lands **gradual paid-to-reported ≈ 0.25–0.35 vs. sudden ≈ 0.60–0.65** — a
  roughly **2× gap** inside a single `peril` — and pulls the blended `water_damage` ratio
  down to ≈ 0.48–0.52. (Directional targets; the realize step measures and firms them.)

An analyst who trusts the `peril` column sees one `water_damage` bucket that pays like the
rest of the book. The teaching point is that the **coverage trigger** — sudden-and-
accidental (covered) vs. gradual wear-and-tear (excluded) — is a real P&C distinction the
claims system records only in the adjuster's narrative, not as a field. To surface the gap
you must parse each loss description, classify the cause, and only then aggregate the
payout: the signal is legible **only after** the prose is read. It is planted by
conditioning water-damage adjudication on a note-native `water_cause`, leaving every other
peril's adjudication untouched.

## How to find it

```sql
-- 1) EXTRACTION: classify each water-loss note from its wording, and pull the estimate.
--    (regex sketch over adjuster_notes.body; an LLM parse would do the same)
--    gradual  <- body ~* 'seepage|gradual|long-term|wear|deterioration|over time|maintenance'
--    sudden   <- body ~* 'burst|sudden|accidental discharge|ruptured|sprang a leak'
--    loss_estimate <- first '$' figure in the note   (== claims.reported_amount, no leak)
with parsed as (
  select n.claim_id,
         case when n.body ~* '(seepage|gradual|long-term|wear|deterioration|over time)' then 'gradual'
              when n.body ~* '(burst|sudden|accidental discharge|ruptured|sprang a leak)' then 'sudden'
         end as cause_from_note
  from adjuster_notes n
  join claims c using (claim_id)
  where c.peril = 'water_damage'
)
-- round-trip check (test layer 1): parsed cause == the withheld answer key
select count(*) filter (where p.cause_from_note is distinct from n.water_cause) as parse_mismatches  -- expect 0
from parsed p join adjuster_notes n using (claim_id);

-- 2) SIGNAL (test layer 2): paid-to-reported by parsed cause — gradual settles ~2x lower
select p.cause_from_note,
       count(*)                                                            as n,
       round(sum(coalesce(pay.paid_amount, 0)) / sum(c.reported_amount), 3) as paid_over_reported
from parsed p
join claims c            using (claim_id)          -- water_damage claims only
left join claim_payments pay using (claim_id)      -- left join: denied/open count as $0
group by p.cause_from_note;
-- target once planted:  sudden ≈ 0.60-0.65   |   gradual ≈ 0.25-0.35   (≈2x gap)
```
