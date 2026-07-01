# Self-pay drives the accounts-receivable balance

- **Signal:** insured claims (Medicare / Medicaid / Commercial) settle in full most
  of the time, but self-pay invoices rarely do — so outstanding accounts-receivable
  concentrates in self-pay far out of proportion to its share of visits.
- **Tables:** `invoices.payer`, `invoices.status`, `invoices.balance`, `invoices.charge`
- **Magnitude:** ≈ 82% of invoices are paid in full overall. Self-pay is only ≈ 12%
  of invoices but ≈ 51% of the total outstanding balance; its open-invoice rate
  ≈ 78% and AR ratio (balance / charge) ≈ 0.39, vs. ≈ 8–13% open and ≈ 0.04–0.06 AR
  ratio for the insured payers.

Every visit is billed, but not every bill is collected. The teaching point is that
"who owes us money" is a payer-mix question, not a volume question: a small slice of
self-pay patients accounts for half the receivable. Group `balance` by `payer` and
the concentration is immediate — the setup for a collections-prioritisation or
payer-contracting discussion. The billing identity `charge = amount_paid + balance`
holds on every row.

## How to find it

```sql
select
    payer,
    count(*)                                   as invoices,
    avg((status = 'outstanding')::int)         as pct_open,     -- self-pay ~0.78
    sum(balance)                               as ar_dollars,
    sum(balance) / sum(charge)                 as ar_ratio      -- self-pay ~0.39
from invoices
group by payer
order by ar_dollars desc;                                      -- self-pay tops the list
```
