# OTA leads overall, but direct wins the upper room classes

- **Signal:** OTA is the single largest booking channel overall — but the channel
  mix flips by room class. For the **upper tiers (Suite / Penthouse) `direct` is the
  modal channel**, while the mass-market Standard / Deluxe rooms lean on the OTA.
- **Tables:** `reservations.channel`, `reservations.room_type`
- **Magnitude:** overall ota ≈ 43%, direct ≈ 34%, corporate ≈ 17%, walk_in ≈ 6%.
  Within Suite+Penthouse, direct ≈ **55%** vs ota ≈ 22% (direct leads ~2.5:1);
  within Standard+Deluxe, ota ≈ 50% vs direct ≈ 28%.

The overall ranking says "we lean on third-party distribution," but that headline
hides who the OTA actually serves: split `channel` by `room_type` and the top of
the ladder tells the opposite story — high-value guests book direct (loyalty /
concierge), not through the OTA. It's the setup for a channel-cost / margin
question: the rooms that pay the OTA commission are the cheap ones, and the
suites — where commission would cost the most — mostly come direct.

## How to find it

```sql
-- overall: ota leads, walk_in last
select channel, count(*) * 1.0 / sum(count(*)) over () as share
from reservations
group by channel order by share desc;         -- ota ~0.43, direct ~0.34, walk_in ~0.06

-- but split by room class: direct is modal for the upper tiers
select case when room_type in ('Suite', 'Penthouse') then 'upper' else 'lower' end as tier,
       channel, count(*) as bookings
from reservations
group by tier, channel
order by tier, bookings desc;                  -- upper → direct on top; lower → ota on top
```
