# Forecast tracks actual occupancy but with ~12% error

- **Signal:** per property per day, `forecast_occupied_rooms` follows
  `actual_occupied_rooms` but is perturbed by noise; neither series ever exceeds
  the property's room capacity.
- **Tables:** `demand_forecast.forecast_occupied_rooms`,
  `demand_forecast.actual_occupied_rooms`, `properties.total_rooms`
- **Magnitude:** forecast = actual × Normal(1.0, 0.12), clipped to
  `[0, total_rooms]` — so ~12% typical forecast error and a hard capacity ceiling.

Actual occupancy is derived from `stays`, then the forecast is the actual blurred
by imperfect foresight. A student should be able to compute a forecast-error
metric (MAPE / bias) and confirm it hovers around 12% with little systematic bias,
and that neither column ever breaches `total_rooms`.

## How to find it

```sql
select avg(abs(forecast_occupied_rooms - actual_occupied_rooms)
           / nullif(actual_occupied_rooms, 0)) as mape          -- ≈ 0.12
from demand_forecast;

select count(*) from demand_forecast d                          -- 0: capacity holds
join properties p using (property_id)
where actual_occupied_rooms > total_rooms
   or forecast_occupied_rooms > total_rooms;
```
