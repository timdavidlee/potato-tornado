# Booked room classes form a demand pyramid

- **Signal:** bookings concentrate in the cheapest room class and thin out up the ladder —
  Standard is the plurality, Penthouse is rare. Booking **volume** runs opposite to nightly
  **price**.
- **Tables:** `reservations.room_type`
- **Magnitude:** Standard ≈ **55%**, Deluxe ≈ **28%**, Suite ≈ **12%**, Penthouse ≈ **5%**.
  The two premium classes together are < 20% of bookings.

Room type is drawn from a fixed weighted mix independent of channel, property, and status, so
the pyramid is stable across every cut. The teaching point pairs with the rate ladder (see
`rate-ladder-holds-within-each-property.md`): the class booked *least* is priced *highest*,
which sets up a revenue-contribution question — do Suites and Penthouses punch above their ~17%
volume share once you weight by `nightly_rate`? Join `reservations.room_type` to
`room_types.nightly_rate` (or aggregate `stays.room_revenue`) to find out.

## How to find it

```sql
-- booking mix is a pyramid: Standard dominates, Penthouse is rare
select room_type, count(*) as bookings,
       count(*) * 1.0 / sum(count(*)) over () as share
from reservations
group by room_type
order by share desc;      -- Standard ≈ 0.55, Deluxe ≈ 0.28, Suite ≈ 0.12, Penthouse ≈ 0.05
```
