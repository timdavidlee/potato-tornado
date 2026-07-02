# Non-refundable rate plans cancel far less than flexible ones

- **Signal:** cancellation/no-show risk is driven by the **rate plan**, not just the booking
  channel. The non-refundable **Advance-Purchase** rate drops off on ~7% of bookings, while
  the flexible **BAR** (Best Available Rate) drops off on ~23% — roughly **3× less** for the
  plan the guest can't get their money back on. Package (~16%) and Corporate-negotiated
  (~13%) sit in between.
- **Tables:** `reservations.rate_plan`, `reservations.status`
- **Magnitude:** drop-off (cancel + no_show) by plan — BAR ≈0.23 ≫ Package ≈0.16 >
  Corporate-negotiated ≈0.13 ≫ Advance-Purchase ≈0.07. Overall rate-plan mix: BAR ≈0.37,
  Advance-Purchase ≈0.29, Package ≈0.19, Corporate-negotiated ≈0.15.

Rate plan is the revenue-management axis, orthogonal to `channel`: the same OTA booking can
be a refundable BAR or a discounted non-refundable Advance-Purchase, and the two behave very
differently at the funnel. The teaching point pairs with
`scenarios/reservation-funnel.md`: the funnel story says "drop-off is an OTA problem," but
adding the rate-plan lens shows *why* a booking is flaky is partly the **commitment the fare
carries** — a non-refundable fare is money already spent, so guests honour it. It sets up the
classic RM trade-off: push discounted non-refundable inventory to cut cancellations, at the
cost of a lower headline rate. The effect is deliberately built on top of the channel
drop-off (a per-plan multiplier on the channel's baseline cancel mass), so the two signals
coexist rather than replace each other.

## How to find it

```sql
-- drop-off by rate plan: Advance-Purchase far below BAR
select rate_plan,
       avg(case when status <> 'honoured' then 1.0 else 0 end) as dropoff,
       count(*) as bookings
from reservations
group by rate_plan order by dropoff desc;
-- BAR ≈0.23, Package ≈0.16, Corporate-negotiated ≈0.13, Advance-Purchase ≈0.07

-- it holds within a channel too (control for the OTA effect): among OTA bookings,
-- Advance-Purchase still cancels far less than BAR
select rate_plan,
       avg(case when status <> 'honoured' then 1.0 else 0 end) as dropoff
from reservations where channel = 'ota'
group by rate_plan order by dropoff desc;   -- BAR on top, Advance-Purchase at the bottom
```
