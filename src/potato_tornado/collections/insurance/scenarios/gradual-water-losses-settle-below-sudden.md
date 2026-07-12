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
  one per claim (= the claim count: 295 at `scale=0.5`, 586 at `scale=1.0`; ~22% are
  `water_damage`). The note narrates the loss cause and renders the reported loss estimate
  in prose. Three name-keyed template variants vary the phrasing.
- **Parse target:** for each note, (a) the loss estimate dollar figure (the first `$`
  figure) and (b) — for water losses — a **sudden vs gradual** classification from the
  wording. Keyword cues: *gradual* → "seepage", "long-term", "gradual", "wear",
  "deterioration", "over time", "maintenance"; *sudden* → "burst", "sudden", "accidental
  discharge", "ruptured", "sprang a leak" (a note carries cues from **one** side only).
  Example (gradual):

  > Inspected POL-0001234 on 2023-06-14. Damage traced to **long-term seepage** behind the
  > wall — consistent with **gradual** deterioration rather than a single event. Initial
  > loss estimate **$7,912**. Coverage position under review given the wear-and-tear
  > exclusion.

  Example (sudden):

  > FNOL for POL-0004567: a supply line **burst** on 2023-06-14, a **sudden accidental
  > discharge** that flooded the area. Initial loss estimate **$6,284**. Clear
  > accidental-discharge trigger, a covered cause.

  Extract `loss_estimate = 7912` and `cause = gradual` from the first; `6284` / `sudden`
  from the second.
- **Ground truth:** the payout side already lives in structured columns — the parsed
  `loss_estimate` reconciles against `claims.reported_amount` (the note renders it rounded
  to the nearest dollar, so the two agree to within \$1), and the paid-to-reported ratio is
  computed from the real `claim_payments.paid_amount` / `claims.status`, **no answer
  leaked**. The one fact with no home elsewhere is the sudden/gradual label: it never
  becomes a structured `claims` column (both `claims`, which tilts adjudication on it, and
  `adjuster_notes`, which renders it, derive it from the same pure seed-keyed function). It
  is shipped as a **withheld** `adjuster_notes.water_cause` answer-key column (`sudden` /
  `gradual` / null for non-water claims) used **only** to check the parser round-trips — it
  is **not** handed to students, who must recover the label from `body`.
- **Tables:** `adjuster_notes.body`, `adjuster_notes.claim_id`,
  `adjuster_notes.water_cause` (withheld key), `claims.peril`, `claims.reported_amount`,
  `claims.status`, `claim_payments.paid_amount`.
- **Magnitude (planted, measured `seed=7`):** water losses split **sudden ≈ 0.57 /
  gradual ≈ 0.43** (`GRADUAL_SHARE = 0.40`; ~57/43 at `scale=1.0`). Gradual claims draw a
  harder adjudication mix (approved 0.22 / partial 0.25 / **denied 0.45** / open 0.08, so
  only ~1-in-4 pays in full) while sudden claims keep the book mix (approved 0.62). That
  lands **gradual paid-to-reported ≈ 0.33 vs. sudden ≈ 0.63** at `scale=1.0` — a **~1.9×
  gap** inside a single `peril` — pulling the blended `water_damage` ratio to ≈ **0.52**
  (from ≈ 0.65 before). At `scale=0.5` the small water subset (~65 claims) is noisier:
  gradual ≈ 0.32, sudden ≈ 0.55 (~1.7× gap), blended ≈ 0.50. Book-level, lowering the
  water slice pulls overall paid-to-reported from ≈ 0.64 to ≈ **0.60** and the loss ratio
  from ≈ 0.65 to ≈ **0.63** (still within the documented 0.62–0.69 band); every other
  peril's adjudication is untouched.

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
