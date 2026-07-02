# Booking drop-off concentrates in the OTA channel

- **Signal:** reservations split ~85% honoured / ~12% cancelled / ~3.5% no-show
  overall, but the drop-off is not spread evenly across channels: the **OTA**
  cancels/no-shows on ~22% of bookings while **walk_in** is almost sticky-solid
  at ~2% — a walk-in guest is already on-site, so can't really cancel or
  no-show. Direct (~10%) and corporate (~14%) sit in between.
- **Tables:** `reservations.channel`, `reservations.status`, `stays.reservation_id`
- **Magnitude:** overall drop-off ≈15%; by channel ota ≈22% ≫ corporate ≈14% >
  direct ≈10% ≫ walk_in ≈2%. (Drop-off is also scaled by `rate_plan` on top of the
  channel — see `scenarios/non-refundable-rates-cancel-less.md`.)

The honoured→stay funnel is the collection's spine: a booking is intent, a stay
is realisation, and there is exactly one `stays` row per honoured reservation
(cancelled / no-show bookings never appear in `stays`). The top-line ~15% drop-off
looks like a single conversion rate — but grouping by channel shows it is really an
OTA problem. This is the natural setup for "where should we tighten the funnel?":
the answer is the OTA (higher cancellation risk, looser commitment), not the
guests who walk up to the desk. It mirrors the channel/room-class link — the OTA
is the mass-market channel (`scenarios/ota-is-the-largest-channel.md`), and it's
also the flakiest.

## How to find it

```sql
select status, count(*) * 1.0 / sum(count(*)) over () as share
from reservations group by status;                 -- 0.85 / 0.12 / 0.035 overall

-- drop-off (cancel + no_show) by channel: OTA on top, walk_in near zero
select channel,
       avg(case when status <> 'honoured' then 1.0 else 0 end) as dropoff
from reservations group by channel order by dropoff desc;
-- ota ≈0.22, corporate ≈0.14, direct ≈0.10, walk_in ≈0.02

-- every matched stay maps to an honoured reservation
select r.status
from stays s join reservations r using (reservation_id)
group by r.status;                                  -- only 'honoured'
```
