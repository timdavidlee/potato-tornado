# Booking drop-off concentrates in the OTA channel

- **Signal:** reservations split ~82% honoured / ~14% cancelled / ~4% no-show
  overall, but the drop-off is not spread evenly across channels: the **OTA**
  cancels/no-shows on ~27% of bookings while **walk_in** is almost sticky-solid
  at ~1.5% — a walk-in guest is already on-site, so can't really cancel or
  no-show. Direct (~12%) and corporate (~15%) sit in between.
- **Tables:** `reservations.channel`, `reservations.status`, `stays.reservation_id`
- **Magnitude:** overall drop-off ≈18%; by channel ota ≈27% ≫ corporate ≈15% >
  direct ≈12% ≫ walk_in ≈1.5%.

The honoured→stay funnel is the collection's spine: a booking is intent, a stay
is realisation, and there is exactly one `stays` row per honoured reservation
(cancelled / no-show bookings never appear in `stays`). The top-line 18% drop-off
looks like a single conversion rate — but grouping by channel shows it is really an
OTA problem. This is the natural setup for "where should we tighten the funnel?":
the answer is the OTA (higher cancellation risk, looser commitment), not the
guests who walk up to the desk. It mirrors the channel/room-class link — the OTA
is the mass-market channel (`scenarios/ota-is-the-largest-channel.md`), and it's
also the flakiest.

## How to find it

```sql
select status, count(*) * 1.0 / sum(count(*)) over () as share
from reservations group by status;                 -- 0.82 / 0.14 / 0.04 overall

-- drop-off (cancel + no_show) by channel: OTA on top, walk_in near zero
select channel,
       avg(case when status <> 'honoured' then 1.0 else 0 end) as dropoff
from reservations group by channel order by dropoff desc;
-- ota ≈0.27, corporate ≈0.15, direct ≈0.12, walk_in ≈0.015

-- every matched stay maps to an honoured reservation
select r.status
from stays s join reservations r using (reservation_id)
group by r.status;                                  -- only 'honoured'
```
