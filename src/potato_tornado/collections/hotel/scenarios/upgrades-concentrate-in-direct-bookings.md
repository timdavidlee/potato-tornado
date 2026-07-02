# Upgrades concentrate in direct bookings

- **Signal:** ~15% of eligible stays take a room upgrade overall, but the upsell is
  not spread evenly across booking channels: **direct** guests upgrade at ~25%,
  more than **3× the OTA** (~8%), with corporate (~14%) and walk_in (~16%) in
  between. The upgrade fee itself is always a *discount* on the rack-rate gap
  (guests pay ~55–80% of `rate_delta × nights`, mean ≈0.68, never the whole gap) —
  that bound holds regardless of channel.
- **Tables:** `room_upgrades.stay_id`, `stays.reservation_id`, `reservations.channel`,
  `room_upgrades.upgrade_fee` / `rate_delta` / `nights`
- **Magnitude:** overall upgrade rate ≈15% of eligible (non-Penthouse) stays; by
  channel direct ≈25% ≫ walk_in ≈16% > corporate ≈14% ≫ ota ≈8%. Discount ratio
  `upgrade_fee / (rate_delta × nights)` ≈0.68 across the board.

The upsell economics are the mechanic (the hotel captures *some* of the class-
difference value, not all of it), but the teachable surprise is *who* takes it:
the front desk works the loyalty/direct relationship, so direct bookers convert
far above the transactional OTA guest. A student pooling all stays sees a flat
~15% conversion; grouping by channel shows the upsell is really a direct-channel
play. This mirrors the channel through-line — the OTA is the largest and flakiest
channel (`scenarios/reservation-funnel.md`) and also the least receptive to an
upgrade.

## How to find it

```sql
-- upgrade rate by channel: direct on top, OTA at the bottom
select r.channel,
       count(u.upgrade_id) * 1.0 / count(*) as upgrade_rate
from stays s
join reservations r using (reservation_id)
left join room_upgrades u using (stay_id)
where s.room_type <> 'Penthouse'          -- Penthouse stays can't upgrade
group by r.channel order by upgrade_rate desc;
-- direct ≈0.25, walk_in ≈0.16, corporate ≈0.14, ota ≈0.08

-- the fee is a discount on the rack-rate gap, regardless of channel
select avg(upgrade_fee / (rate_delta * nights)) as discount_ratio,      -- ≈ 0.68
       count(*) filter (where upgrade_fee >= rate_delta * nights) as full_price  -- 0
from room_upgrades;
```
