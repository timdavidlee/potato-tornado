# Paid-acquired subscribers churn faster

- **Signal:** the acquisition channel a subscriber came in through predicts churn —
  subscribers from paid channels (`paid_search`, `social`) cancel at several times
  the rate of organically-acquired ones (`organic`, `referral`).
- **Tables:** `subscribers.acquisition_channel`, `subscriptions.status` (join on `subscriber_id`)
- **Magnitude:** cancelled-rate ≈ `organic` 0.10 / `referral` 0.11 / `partner` 0.20 /
  `social` 0.32 / `paid_search` 0.38 — the paid pair runs ~3× the organic pair.

Churn is deliberately *not* flat across the base: each subscriber's cancel
probability is the base rate scaled by an acquisition-channel multiplier (and a
billing-cadence one — see `annual-plans-retain-better.md`). The teaching point is
that a healthy top-line retention number hides a large gap by acquisition source,
so blending channels together masks that paid acquisition buys weaker retention —
a segmentation / cohort-quality exercise. Overall cancelled share still lands
≈0.21, so the signal only shows up once you split by channel.

## How to find it

```sql
-- cancelled-rate by acquisition channel: paid channels churn far more.
select s.acquisition_channel,
       avg((sub.status = 'cancelled')::int) as cancel_rate  -- organic ~0.10 … paid_search ~0.38
from subscriptions sub
join subscribers s using (subscriber_id)
group by s.acquisition_channel
order by cancel_rate;
```
