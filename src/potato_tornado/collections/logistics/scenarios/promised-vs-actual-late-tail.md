# Promised-vs-actual SLA: most on time, a right-skewed late tail

- **Signal:** comparing the plan (`promised_date`) to the actual
  (`actual_delivery_date`), most delivered parcels meet or beat the promise, and the
  parcels that run late form a right-skewed tail — a few days late is common, a week
  late is the edge. The plan-vs-actual pairing is the point: neither table alone
  tells you whether the SLA was met.
- **Tables:** `deliveries.days_late`, `deliveries.actual_delivery_date`,
  `deliveries.status`, `shipments.promised_date`.
- **Magnitude:** ≈ **86%** of delivered parcels are on time (`days_late <= 0`); the
  late minority (~**14%**) averages ≈ **+2.6 days** and tops out at **+7**. Early
  arrivals pull the overall mean `days_late` slightly below zero. Non-delivered rows
  (`returned_to_sender` / `lost`, ~3.6% combined) carry null
  `actual_delivery_date` / `days_late` and are excluded.

`days_late` is a signed integer: negative (or zero) is on time, positive is late,
and the late side is a clamped Poisson-ish draw so it decays quickly past a couple
of days. The teaching point is the plan-vs-actual join and reading a signed,
right-skewed lateness distribution: a mass at/below zero with a thin positive tail,
not a symmetric spread. Pair it with `on-time-degrades-with-zone.md` to see *where*
the late tail concentrates.

## How to find it

```sql
-- lateness histogram: mass at/below 0, thin right tail out to +7
select days_late, count(*) as n
from deliveries
where status = 'delivered'
group by days_late
order by days_late;

-- summary: ~86% on time, late tail mean ≈ +2.6d
select avg((days_late <= 0)::int)                        as on_time_rate,   -- ≈ 0.86
       avg(days_late) filter (where days_late > 0)       as late_mean,      -- ≈ 2.6
       max(days_late)                                    as worst           -- 7
from deliveries
where status = 'delivered';
```
