# Signature requirement concentrates in the fast service tiers

- **Signal:** the ~9% overall `signature_required` rate is not uniform — it is a
  strong function of `service_level`, climbing ≈ 6× from ground to overnight. The
  flat top-line hides a premium-tier concentration: signatures (a high-value /
  higher-liability handling marker) ride the fast, expensive tiers, not the bulk
  ground volume.
- **Tables:** `shipments.signature_required`, `shipments.service_level`,
  `shipments.weight_kg`.
- **Magnitude:** overall ≈ **0.09**; by tier **ground ≈ 0.05 / express ≈ 0.16 /
  overnight ≈ 0.31** — a ≈ **6×** spread across the ladder. There is a secondary
  weight lever (design ≈ 0.55 for parcels ≥ 20 kg), but ≥ 20 kg parcels are a thin
  tail of the lognormal weight draw (≈ 0.2% of rows, ~18 at `scale=1.0`), so the
  heavy bump is real in the generator yet barely visible in aggregate — the
  *service-tier* gradient is where the observable signal lives. (Measured: `seed=7,
  scale=1.0`; already produced by today's generator.)

`signature_required` is drawn from a low base (0.05) plus a per-tier bump
(ground +0, express +0.10, overnight +0.25) plus a heavy-parcel bump — so premium
shipments, which are already rarer and pricier, are also the ones that demand a
signature. The teaching point mirrors `on-time-degrades-with-zone.md`: a single
top-line rate (~9%) is misleading, and the real story is a monotone gradient across
a slice — here `service_level` instead of `dest_zone`. It also composes downstream:
because a signature-required parcel takes the `signature` last-mile path,
`deliveries.delivery_method = 'signature'` inherits the same tier concentration, so
the two columns tell one consistent story about premium handling.

## How to find it

```sql
-- signature rate climbs ~6x across the service ladder (top-line ~9% is misleading)
select service_level,
       avg(signature_required::int) as sig_rate,   -- ground ≈ 0.05, express ≈ 0.16, overnight ≈ 0.31
       count(*)                     as n
from shipments
group by service_level
order by sig_rate;

-- overall vs. the premium tiers side by side
select avg(signature_required::int)                                       as overall,     -- ≈ 0.09
       avg(signature_required::int) filter (where service_level = 'overnight') as overnight,   -- ≈ 0.31
       avg(signature_required::int) filter (where service_level = 'ground')    as ground       -- ≈ 0.05
from shipments;
```
