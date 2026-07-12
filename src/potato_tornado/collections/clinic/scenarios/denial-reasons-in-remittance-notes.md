# Why a claim was denied is buried in the remittance note — and it splits by payer

- **Signal:** among denied claims, the *reason* for the denial concentrates by payer in a
  way the flat denial rate hides. **Medicaid denials are overwhelmingly missing-prior-
  authorization** failures, while **Commercial denials are dominated by coding / bundling**
  problems — two payers, two completely different fixes (get the auth vs. recode the claim),
  and the reason lives only in the free-form remittance note, not in any structured column.
- **Documents:** `remittance_notes.body` · doc type **note** (a billing / remittance-advice
  remark, one per denied claim) · rough count ≈ 8% of invoices (one row per invoice with
  `claim_status = 'denied'` — ≈ 200 at `scale=1.0`, ≈ 100 at `scale=0.5`, well above the
  floor of 1).
- **Parse target:** from each note extract three things — the **denied dollar amount**, the
  **payer**, and the **denial reason** (a CARC-style code / phrase). Example snippet:

  > Remittance advice — claim `INV-0001234` (Medicaid). Billed $340.00; allowed $255.00 after
  > contractual adjustment. Line denied: **$85.00 — CO-197, authorization/precertification
  > absent.** Resubmit with prior auth on file.

  pulls `denied_amount = 85.00`, `payer = "Medicaid"`, `reason_code = "CO-197"`
  (prior authorization). A second phrasing renders the same fields differently, e.g.
  *"EOB for INV-0002100, payer Commercial: of the $180.00 charge, $72.00 was not paid —
  CO-97, service bundled into the primary procedure and not separately payable."*
- **Ground truth:**
  - The **denied amount** parsed from the note reconciles against the existing
    `invoices.denied_amount` column, and the **payer** against `invoices.payer` — the numeric
    + categorical anchors that prove the parse is faithful, **with no leak** (the body merely
    *renders* those columns).
  - The **reason** is the signal and exists in **no** current column, so it ships as a
    `remittance_notes.denial_reason_code` **answer-key column beside `body`, withheld** when
    documents are handed to students. **(to be planted)**
- **Tables:** `remittance_notes.body`, `remittance_notes.denial_reason_code` (withheld),
  `invoices.denied_amount`, `invoices.payer`, `invoices.claim_status`
  (join `remittance_notes.invoice_id → invoices.invoice_id`).
- **Magnitude (to be planted; targets to firm up at realize time):** the overall denial rate
  is unchanged at ≈ **8%** (this scenario adds only a reason, not more denials). The reason
  mix is keyed to payer:

  | payer | prior-auth (CO-197) | bundling (CO-97) | documentation (CO-16) | med-necessity / fee-schedule |
  |---|---|---|---|---|
  | Medicaid | ≈ **45%** | ≈ 15% | ≈ 25% | ≈ 15% (CO-50) |
  | Commercial | ≈ 15% | ≈ **40%** | ≈ 20% | ≈ 25% (CO-45) |
  | Medicare | ≈ 15% | ≈ 30% | ≈ **35%** | ≈ 20% (CO-50) |

  Headline: Medicaid's prior-auth share (≈ 45%) is ≈ **3×** Commercial's (≈ 15%), and
  Commercial's bundling share (≈ 40%) is ≈ **3×** Medicaid's (≈ 15%). Self-pay denials are
  negligible (≈ 9 rows at any scale — an insurer isn't adjudicating a self-pay claim) and sit
  outside the signal.

An analyst is handed a folder of remittance remarks, not a clean `denial_reason` column: the
reason is legible **only after parsing the prose**. Extract `(payer, denied_amount, reason)`
from each note, reconcile the amount against `invoices.denied_amount` to prove the parse is
right, then group the reason by payer and the split jumps out. The teaching point is that the
flat "≈ 8% of claims are denied" headline — and even the payer-level denial *rate* in
[`adjudication-varies-by-payer.md`](adjudication-varies-by-payer.md) — tells you *how much* is
denied but nothing about **why**, and the *why* dictates a different intervention per payer:
Medicaid denials are a front-desk authorization problem (fixable before the visit), while
Commercial denials are a coding / bundling problem for a biller. This scenario is the
*qualitative* companion to the dollars-only adjudication signal: same denied claims, but the
insight lives in text.

## How to find it

```sql
-- 1) EXTRACTION — parse (payer, denied_amount, reason_code) out of the free-form note.
--    Reconcile the parsed amount against the real column to prove the parse is faithful
--    (this is layer (a) of the two-layer test; no answer is leaked into `body`).
with parsed as (
  select
    r.invoice_id,
    -- denied dollars: the "$NN.NN ... denied / not paid" figure in the note
    cast(regexp_extract(r.body, '\$([0-9][0-9,]*\.[0-9]{2})[^$]*(?:denied|not paid)', 1)
         as double)                                            as parsed_denied,
    -- reason: the CARC code, or fall back to the phrase keywords
    regexp_extract(r.body, 'CO-([0-9]+)', 1)                   as reason_code
  from remittance_notes r
)
select count(*)                                                   as notes,
       sum((abs(p.parsed_denied - i.denied_amount) < 0.01)::int)  as reconciled  -- == notes
from parsed p
join invoices i using (invoice_id);

-- 2) AGGREGATION — reason mix by payer. The parsed reason concentrates differently per payer.
select i.payer,
       p.reason_code,
       count(*) * 1.0 / sum(count(*)) over (partition by i.payer) as share
from parsed p
join invoices i using (invoice_id)
where i.payer <> 'Self-pay'
group by i.payer, p.reason_code
order by i.payer, share desc;
-- Medicaid:   CO-197 (prior auth)     share ≈ 0.45  (vs ≈ 0.15 for Commercial)
-- Commercial: CO-97  (bundling)       share ≈ 0.40  (vs ≈ 0.15 for Medicaid)
-- Medicare:   CO-16  (documentation)  share ≈ 0.35
```
