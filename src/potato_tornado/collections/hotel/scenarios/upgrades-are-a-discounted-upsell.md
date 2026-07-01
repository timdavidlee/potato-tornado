# Room upgrades are sold below the rack-rate difference

- **Signal:** an upgrade's `upgrade_fee` is always a *discount* on the full
  class-difference — guests pay ~55–80% of `rate_delta × nights`, never the whole gap.
- **Tables:** `room_upgrades.upgrade_fee`, `room_upgrades.rate_delta`,
  `room_upgrades.nights`, `room_upgrades.from_room_type` / `to_room_type`
- **Magnitude:** mean `upgrade_fee / (rate_delta × nights)` ≈ **0.68** (bounded 0.55–0.80);
  ~**15%** of eligible stays upgrade (everything but a Penthouse stay is eligible).

An upgrade is its own event: the guest checked in on `from_room_type` and moved one (or
occasionally two) rungs up the ladder to `to_room_type` for a fee charged on arrival. The
teaching point is the upsell economics — the hotel captures *some* of the class-difference
value, not all of it, so the fee sits strictly below the rack-rate delta. A student should
discover that the "cost of an upgrade" is not the sticker-price difference between room
classes.

## How to find it

```sql
select avg(upgrade_fee / (rate_delta * nights)) as discount_ratio,   -- ≈ 0.68
       count(*) filter (where upgrade_fee >= rate_delta * nights) as full_price   -- 0
from room_upgrades;

-- upgrades always move up the ladder, and ~15% of stays get one
select count(*) * 1.0 / (select count(*) from stays) as upgrade_rate  -- ≈ 0.15
from room_upgrades;
```
