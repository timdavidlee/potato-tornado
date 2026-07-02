# The effective tax load is lighter across Iberia

- **Signal:** the tax wedge on a stay (`stays.taxes_fees` as a share of `stays.room_revenue`)
  is materially *lighter* in the Iberian properties than in the Western-European ones —
  ≈8.5% vs ≈10.9%. It happens because accommodation VAT and the city tourist tax are keyed to
  the property's geography: Portugal charges a reduced 6% VAT (vs 10% in Spain/France/Italy)
  and Spanish cities levy no tourist tax, so the two Iberian countries sit at the bottom of
  the ladder while France and Italy stack a per-night city tax on top of the full 10% VAT.
- **Tables:** `stays.taxes_fees`, `stays.room_revenue`, `properties.country`,
  `properties.region`, `properties.city`
- **Magnitude:** effective rate `taxes_fees / room_revenue` — Portugal ≈0.072 < Spain ≈0.100
  < Italy ≈0.109 < France ≈0.110; rolled up by region, Iberia ≈0.085 vs Western Europe ≈0.109
  (overall ≈0.096). The VAT floor is exact (6% / 10%); the city tax adds a few tenths of a
  point on top (a flat EUR 2.0/night in Lisbon & Porto, EUR 1.5 Lyon, EUR 1.4 Turin, EUR 0 in
  the Spanish cities), and because it's a flat per-night charge its *percentage* bite is a
  touch larger on cheaper room-nights.

`taxes_fees` is the wedge that separates the guest's gross bill from the net room charge:
`room_revenue` deliberately stays **net of tax**, so the industry KPIs read straight off it —
`ADR = room_revenue / room-nights`, `RevPAR = room_revenue / available room-nights` (with
`room_types.room_count`), `TRevPAR` once ancillary spend is folded in. The teaching point is
twofold: first, a student who computes ADR on the tax-inclusive figure overstates it by the
effective rate (≈10%); second, that overstatement is not uniform — it varies by country and
region, so a naive gross-based ADR would make the Iberian properties look ~2 points cheaper
relative to peers than they really are. The signal ties the geography rollup
(`country` / `region`) to a real revenue consequence.

## How to find it

```sql
-- effective tax rate by region: Iberia lighter than Western Europe
select p.region,
       sum(s.taxes_fees) / sum(s.room_revenue) as eff_rate
from stays s join properties p using (property_id)
group by p.region
order by eff_rate;             -- Iberia ~0.085, Western Europe ~0.109

-- by country: Portugal is the outlier low (reduced 6% VAT, plus a small city tax)
select p.country,
       sum(s.taxes_fees) / sum(s.room_revenue) as eff_rate
from stays s join properties p using (property_id)
group by p.country
order by eff_rate;             -- Portugal ~0.072 < Spain ~0.100 < Italy ~0.109 < France ~0.110

-- net vs gross ADR: gross-inclusive ADR overstates the true (net) ADR by the effective rate
select sum(room_revenue) / sum(actual_nights)                 as adr_net,
       sum(room_revenue + taxes_fees) / sum(actual_nights)    as adr_gross
from stays;                    -- adr_gross ~1.10x adr_net
```
