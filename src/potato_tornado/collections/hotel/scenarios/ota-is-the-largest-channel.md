# OTA is the largest booking channel

- **Signal:** bookings skew toward the OTA (online travel agency) channel, which
  is the single largest source; walk-ins are rare.
- **Tables:** `reservations.channel`
- **Magnitude:** ota ≈ 44%, direct ≈ 34%, corporate ≈ 16%, walk_in ≈ 6%.

The channel mix is a fixed weighted distribution. Grouping reservations by channel
should rank OTA first and walk-in last — a realistic shape for a mid-market hotel
that leans on third-party distribution. Pairs naturally with revenue questions
(is the highest-volume channel also the highest-value?).

## How to find it

```sql
select channel, count(*) as bookings,
       count(*) * 1.0 / sum(count(*)) over () as share
from reservations
group by channel
order by bookings desc;                  -- ota first (~0.44), walk_in last (~0.06)
```
