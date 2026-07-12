# How much a claim collects depends on its payer, not its charge

- **Signal:** two identical charges settle for different amounts depending on who is
  billed — the contractual write-down (`adjustment_amount`) and the denial rate
  (`claim_status = 'denied'`) both rise as you move from Commercial to Medicare to
  Medicaid, so the realised reimbursement (`allowed / charge`) is lowest for Medicaid.
  The gross charge (`charge`, driven by procedure mix — see
  `charge-varies-by-procedure.md`) says nothing about how much the clinic actually
  keeps.
- **Tables:** `invoices.payer`, `invoices.adjustment_amount`, `invoices.denied_amount`,
  `invoices.claim_status`, `invoices.charge`
  (derived: `allowed = charge − adjustment_amount − denied_amount`)
- **Magnitude:** measured at seed 7 / scale 0.5 (payer-weighted averages hold the flat
  marginals: adjustment ≈ 14% of charge, denial ≈ 8%, allowed ≈ 0.84):

  | payer | adjustment (% of charge) | denial rate | allowed / charge |
  |---|---|---|---|
  | Commercial | ≈ 10% | ≈ 7% | ≈ 0.88 |
  | Medicare | ≈ 16% | ≈ 7% | ≈ 0.82 |
  | Medicaid | ≈ 25% | ≈ 15% | ≈ 0.71 |
  | Self-pay | ≈ 3% | ≈ 5% | ≈ 0.95 |

  The reimbursement `allowed / charge` falls Commercial → Medicare → Medicaid, and
  self-pay sits highest (no insurer contract writes anything down) — the inversion the
  scenario teaches. (Denial rates on the small per-payer samples are noisy; the planted
  denial *probabilities* are 5% / 8% / 15% / 3%, with Medicaid clearly highest.)

The adjudication columns (`adjustment_amount`, `denied_amount`, `claim_status`)
currently ship **flat and independent of `payer`** — see the "Payer adjudication is
flat" note in `realism-guidance.md` and item 4 in `TODO.md`. The signal to plant:
key the adjustment fraction and denial probability off `payer` in
`_adjudication_split` (`tables/invoices.py`) so Medicaid writes down and denies the
most and Commercial the least, keeping the payer-weighted marginals at their current
levels. The realiser must preserve `allowed = charge − adjustment_amount −
denied_amount ≥ 0` (per-payer fraction caps whose sum stays < 1) and leave the
separate `charge = amount_paid + balance` billing identity untouched.

The teaching point is the **allowed ≠ collected** distinction. This is the *insurer
side* of receivables and is deliberately distinct from `revenue-and-ar.md`, which is
the *patient side* (self-pay leaves the largest **balance**). Note the inversion the
target table plants: self-pay has the **highest** `allowed / charge` (no insurer
contract writes anything down) yet the **worst** collection — nothing is written off,
but the patient still doesn't pay, so it ages into AR. So "who reimburses least"
(Medicaid, by contract) and "who leaves the most unpaid" (self-pay, by non-payment)
are two different payer stories on the same invoice. Grouping the adjudication funnel
by payer is the setup for a payer-contracting / service-mix discussion the flat
top-line can't support.

## How to find it

```sql
-- Reimbursement rate falls from Commercial to Medicaid; self-pay is written down least.
select
    payer,
    count(*)                                                   as invoices,
    avg(adjustment_amount / charge)                            as adj_frac,       -- Medicaid ~0.25, Commercial ~0.10
    avg((claim_status = 'denied')::int)                        as denial_rate,    -- Medicaid ~0.15, Commercial ~0.05
    avg((charge - adjustment_amount - denied_amount) / charge) as allowed_ratio   -- Medicaid ~0.71, Commercial ~0.88
from invoices
group by payer
order by allowed_ratio;   -- Medicaid at the bottom, self-pay/Commercial at the top

-- The overall (payer-blind) adjudication marginals are unchanged by the tilt:
select
    avg(adjustment_amount / charge)     as adj_frac,     -- ~0.14 overall
    avg((claim_status = 'denied')::int) as denial_rate   -- ~0.08 overall
from invoices;
```
