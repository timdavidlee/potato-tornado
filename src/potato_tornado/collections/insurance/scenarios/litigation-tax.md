# The litigation tax: litigated claims cost more and settle slower

- **Signal:** the ~10% of claims that go **litigated** (attorney representation) are a
  materially heavier and slower subset — they run a higher `paid_amount` (a severity
  loading) **and** a longer claim → settlement / adjudication cycle than their
  non-litigated peers. Litigation incidence itself stays a flat base rate; the surprise
  is the two-dimensional *tax* that rides on the flag once you slice by it.
- **Tables:** `claims.litigated`, `claims.reported_amount`,
  `claim_payments.paid_amount`, `claim_payments.settlement_days`,
  `claim_status_history` (`reported → terminal` elapsed days per claim).
- **Magnitude (planted; measured full scale over seeds 7/13/21):** litigated ≈ **11%** of
  claims — a flat base rate (0.09–0.13 across seeds); the flag's *incidence* is unchanged, only
  its consequences are coupled. The tax is two-dimensional:
  - **Severity:** litigated mean `paid_amount` ≈ **1.8×** non-litigated (full-scale range
    **1.6–2.0×** across seeds; e.g. seed 7 ≈ 1.82×). Planted by scaling `reported_amount`
    **×2.2** on litigated claims so `paid_amount` follows up **within the payout cap** — the
    cap *compresses* the realized paid ratio below the reported multiplier (a litigated claim
    scaled past its `coverage_limit` pays the capped amount, not ×2.2). The `scale=0.5` seed-7
    test fixture reads a noisier ≈ **2.3×** on 27 litigated settled claims (small-n).
  - **Cycle time:** litigated settle ≈ **1.75–1.9×** slower — `claim_payments.settlement_days`
    ≈ **42 days** vs ≈ **25** (stretched **×1.75**), and the `claim_status_history`
    reported→terminal span ≈ **35 days** vs ≈ **18** (≈1.9×, both lifecycle gaps stretched
    **×1.75**).

Litigation is the classic P&C "tax": an attorney on the file both inflates the ultimate
payout and drags out the settlement clock. `claims.litigated` stays a flat ~11% Bernoulli in
*incidence*, but its severity and cycle-time *consequences* are now coupled: litigated claims
carry a heavier `reported_amount` (which flows into `paid_amount` within the existing payout
cap — so the payout-bound invariant is untouched) and a longer `claim_payments.settlement_days`
plus `claim_status_history` cycle. This relaxes the severity-independence simplification for
this one flag. The teaching point is a covariate that moves *two* metrics at once: a student
who slices loss cost by litigation status sees both a fatter mean severity and a longer tail on
cycle time — the reason claims teams triage litigated files differently. (A side effect worth
knowing: because litigated claims are ~11% of the book and now cost more, the overall loss
ratio and mean severity sit a few points higher than a litigation-free book would — see the
matching notes in `realism-guidance.md`.)

## How to find it

```sql
-- litigated claims: heavier payout AND slower settlement than non-litigated peers
-- (planted: ≈1.8x mean paid and ≈1.75x settlement days vs non-litigated)
select c.litigated,
       count(*)                               as n,
       round(avg(pay.paid_amount), 0)         as mean_paid,      -- litigated ≈1.8x non-litigated
       round(avg(pay.settlement_days), 1)     as mean_settle_days -- litigated ≈1.75x (~42 vs ~25 days)
from claims c
join claim_payments pay using (claim_id)      -- settled claims only
group by c.litigated;

-- corroborate the slower cycle from the lifecycle log (reported -> terminal elapsed days)
with span as (
  select claim_id,
         date_diff('day', min(changed_at), max(changed_at)) as cycle_days
  from claim_status_history group by claim_id
)
select c.litigated, round(avg(s.cycle_days), 1) as mean_cycle_days  -- litigated ≈1.9x (~35 vs ~18 days)
from claims c join span s using (claim_id)
group by c.litigated;
```
