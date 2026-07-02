# Revenue per visit is driven by procedure mix, not visit count

- **Signal:** the billed charge per visit varies several-fold across visit types,
  so a low-volume, high-charge procedure can out-earn a high-volume routine one —
  revenue concentrates in the expensive procedures out of proportion to their share
  of visits.
- **Tables:** `invoices.charge`, `visits.visit_type` (join `invoices.visit_id → visits.visit_id`)
- **Magnitude:** mean charge per visit spans ≈ $90 (Telehealth) to ≈ $340 (Minor
  Procedure) — a ~3.8× spread. Minor Procedure is only ≈ 9–10% of visits but ≈ 20% of
  gross charges (≈ 2× its volume share); Telehealth is ≈ 9% of visits but only ≈ 5% of
  charges. Follow-up is the volume leader (≈ 32–35% of visits) yet, at ≈ $110 each,
  contributes only ≈ 24% of revenue.

Every visit is billed, but the bills are not the same size. This is the gross-revenue
companion to [`revenue-and-ar.md`](revenue-and-ar.md): that doc asks *who pays* (payer
mix drives the receivable), this one asks *what earns* (procedure mix drives the charge).
The teaching point is that a clinic's revenue is a weighted sum, not a headcount — the
schedule that maximises visit volume is not the one that maximises billings. Group charges
by `visit_type` and the concentration is immediate: the setup for a service-line or
capacity-allocation discussion. The charge is deterministic from each visit type's base
charge (`constants.VISIT_TYPES`) with mild ±8% variation, so today's generator already
produces this signal.

## How to find it

```sql
select
    v.visit_type,
    count(*)                                           as visits,
    count(*) * 1.0 / sum(count(*)) over ()             as visit_share,
    avg(i.charge)                                      as avg_charge,   -- ~90 .. ~340
    sum(i.charge)                                      as gross_rev,
    sum(i.charge) / sum(sum(i.charge)) over ()         as rev_share     -- Minor Proc ~0.17 on ~0.08 of visits
from invoices i
join visits v on v.visit_id = i.visit_id
group by v.visit_type
order by avg_charge desc;
```
