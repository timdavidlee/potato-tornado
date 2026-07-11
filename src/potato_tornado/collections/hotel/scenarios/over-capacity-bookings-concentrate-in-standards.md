# Over-capacity bookings concentrate in Standard rooms

- **Signal:** a party often books a room rated for fewer guests than the party holds, and this
  over-capacity booking is **not spread evenly across the ladder** — it concentrates in the
  cheap **Standard** rooms and vanishes at the top. The twist is an inversion: mean party size
  *rises* up the class ladder, yet the share of bookings that *exceed* the room's rated
  capacity *falls* down it, because `max_occupancy` climbs faster than party size does.
- **Tables:** `reservations.party_size`, `reservations.room_type`, `room_types.max_occupancy`
  (fixed lookup off `room_type`: Standard 2 / Deluxe 3 / Suite 4 / Penthouse 6)
- **Magnitude:** overall ≈ **22%** of bookings carry a `party_size` above the room's
  `max_occupancy`; by class Standard ≈ **0.30** ≫ Deluxe ≈ **0.14** > Suite ≈ **0.09** ≫
  Penthouse **0.00** (exact — a Penthouse seats 6 and `party_size` is capped at 6, so it can
  never over-fill). Mean party size runs the *opposite* way: Standard ≈2.1 < Deluxe ≈2.3 <
  Suite ≈2.7 < Penthouse ≈2.8.

`party_size` is drawn `Poisson(λ)+1` with `λ` keyed to **room class** (larger rooms draw larger
parties), while `max_occupancy` is a fixed capacity ladder (2 / 3 / 4 / 6). The two are drawn
independently — `party_size` is *not* capped at the room's rated capacity — so a three-guest
Standard booking is legal and common. The teaching point is the inversion: a naive analyst who
sees party size climbing up the ladder assumes the *capacity pressure* is at the top, but
relative to what each room seats, the pressure is squarely at the **bottom** — Standards are
over-filled three times as often as Suites, and Penthouses never are. It's the classic
absolute-vs-relative-to-capacity trap, and a concrete upsell hook: the over-capacity Standard
guests are exactly the ones a front desk would move up a class.

## How to find it

```sql
-- over-capacity rate by class: highest for Standard, exactly zero for Penthouse
with cap as (select distinct room_type, max_occupancy from room_types)
select r.room_type,
       avg(r.party_size)                                              as mean_party,   -- rises up the ladder
       c.max_occupancy,
       avg(case when r.party_size > c.max_occupancy then 1.0 else 0 end) as over_rate  -- falls down it
from reservations r
join cap c using (room_type)
group by r.room_type, c.max_occupancy
order by c.max_occupancy;
-- Standard 0.30, Deluxe 0.14, Suite 0.09, Penthouse 0.00

-- overall ~22% of bookings exceed the room's rated capacity
with cap as (select distinct room_type, max_occupancy from room_types)
select avg(case when r.party_size > c.max_occupancy then 1.0 else 0 end) as over_rate  -- ≈ 0.22
from reservations r
join cap c using (room_type);
```
