# Weekend forecasts are far less accurate than weekday ones

- **Signal:** per property per day, `forecast_occupied_rooms` follows
  `actual_occupied_rooms` but is perturbed by noise — and the noise is **not
  uniform**: weekend demand is harder to call, so weekend forecasts carry a much
  wider error band than weekday ones. Neither series ever exceeds room capacity.
- **Tables:** `demand_forecast.forecast_occupied_rooms`,
  `demand_forecast.actual_occupied_rooms`, `demand_forecast.forecast_date`,
  `properties.total_rooms`
- **Magnitude:** forecast = actual × Normal(1.0, `sd`), clipped to
  `[0, total_rooms]`, with `sd` = **0.09 on weekdays** and **0.22 on weekends**.
  Measured absolute % error (MAPE) ≈ **9% on weekends vs <1% on weekdays** — a
  roughly 10× gap (weekday rounding of low occupancy compresses its error further).

Actual occupancy is derived from `stays`, then blurred by imperfect foresight. A
flat "the forecast is roughly right" misses where it goes wrong: bucket by day of
week and the weekend rows carry nearly all the error. It's the setup for a "when
is the forecast least trustworthy?" question — the answer is weekends, the days
that matter most for staffing and pricing. The capacity ceiling still holds:
neither column ever breaches `total_rooms`.

## How to find it

```sql
-- weekend forecast error dwarfs weekday error
select case when dayofweek(forecast_date) in (0, 6) then 'weekend' else 'weekday' end as day_kind,
       avg(abs(forecast_occupied_rooms - actual_occupied_rooms)
           / nullif(actual_occupied_rooms, 0))                as mape
from demand_forecast
group by day_kind;                             -- weekend ~0.09, weekday <0.01

select count(*) from demand_forecast d                          -- 0: capacity holds
join properties p using (property_id)
where actual_occupied_rooms > total_rooms
   or forecast_occupied_rooms > total_rooms;
```
