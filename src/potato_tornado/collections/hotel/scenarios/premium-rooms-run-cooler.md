# Premium rooms run at lower occupancy than standards

- **Signal:** occupancy per room class runs *opposite* to the price ladder. Standards are the
  hottest class (~9.7% of room-nights filled), and utilization falls all the way down to the
  **Penthouse (~5.8%)** — premium rooms sit emptier. It happens because the physical
  **inventory mix is more top-heavy than demand**: the group built proportionally more
  suites/penthouses (`room_types.room_count`) than the booking mix (`reservations.room_type`)
  fills, so the premium classes carry idle supply.
- **Tables:** `room_types.room_count`, `room_types.room_type`, `stays.room_type`,
  `stays.actual_nights`
- **Magnitude:** utilization (room-nights sold ÷ room_count × days) — Standard ≈0.097 >
  Deluxe ≈0.092 > Suite ≈0.068 > Penthouse ≈0.058 (Standard runs ~1.7× the Penthouse). The
  inventory mix is Standard 0.50 / Deluxe 0.27 / Suite 0.15 / Penthouse 0.08 vs the booking
  mix 0.55 / 0.28 / 0.12 / 0.05.

`room_count` splits each property's `total_rooms` across the four classes (summing exactly to
`total_rooms`), which is what makes **per-class occupancy and RevPAR** computable — before it,
inventory was property-level only. The teaching point is the classic capacity-vs-demand
mismatch: the headline says suites are premium, but the by-class occupancy shows the group is
over-built at the top. It's the setup for a RevPAR-by-class question — a premium room at low
occupancy can still out-earn a full standard, so the fix isn't obvious from occupancy alone.

## How to find it

```sql
-- utilization by class: sold room-nights vs available room-nights
with sold as (
  select room_type, sum(actual_nights) as nights_sold from stays group by room_type
),
avail as (
  select room_type, sum(room_count) as rooms from room_types group by room_type
)
select s.room_type, s.nights_sold, a.rooms,
       s.nights_sold * 1.0 / (a.rooms * (select date_diff('day', min(check_in_date), max(check_in_date))
                                         from reservations)) as util
from sold s join avail a using (room_type)
order by util desc;   -- Standard on top (~0.097), Penthouse at the bottom (~0.058)

-- the cause: inventory is more top-heavy than bookings
select room_type, sum(room_count) * 1.0 / sum(sum(room_count)) over () as inv_share
from room_types group by room_type;   -- Suite 0.15 / Penthouse 0.08 vs booked 0.12 / 0.05
```
