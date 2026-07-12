# Refund exposure tracks the parsed guarantee terms, not carrier reliability

- **Signal:** each carrier's rate card states an **on-time refund guarantee** — "we
  refund the full shipping charge if a parcel is delivered *N or more* days after its
  promised date" — and the threshold `N` differs by carrier, tighter for the premium
  air carriers and looser for the budget ground carrier. Because that threshold lives
  **only in the rate-card prose**, refund liability cannot be computed from any column
  until the guarantee is parsed. Once it is, the surprise lands: refund exposure
  (refunded dollars ÷ shipping revenue) does **not** rank with carrier `reliability`.
  The *least* reliable carrier (Coyote, worst on-time) sheds most of its misses under
  its own loose 3-day bar and lands **among the lowest** refund-to-revenue, while
  tightly-guaranteed carriers pay out on near-misses a looser policy would ignore. Who
  bleeds refunds is set by the guarantee terms, not the on-time record.
- **Documents:** `carrier_policies.body` — a **policy / rate-card document** (rules
  doc), one per carrier (≈ 5 rows, 1:1 with `carriers`, FK `carrier_id`; a fixed dim
  set, not scaled). Each renders the carrier's pricing terms and its service-guarantee
  clause as free-form prose.
- **Parse target:** from each rate card, extract (a) the **guarantee threshold** `N`
  (the days-late that triggers a full refund) and (b) the pricing terms (`base_rate`,
  `per_kg_rate`, `fuel_surcharge_pct`) used to prove the parser reads real rendered
  facts. Example prose:

  > **Coyote Ground — Rate Card & Service Guarantee.** Charges are billed at a **$2.25**
  > base plus **$0.70/kg** of actual weight; an **8.0%** fuel surcharge is added. Ground
  > service. *Guarantee:* shipping fees are refunded only when delivery runs **3 or more
  > days** behind the promised date.

  pulls `guarantee_days = 3`, `base_rate = 2.25`, `per_kg_rate = 0.70`,
  `fuel_surcharge_pct = 0.08`. A premium card ("… refunded if a parcel arrives **1+
  day(s) late** …") pulls `guarantee_days = 1`. Phrasing varies across 2–3 templates,
  so the extractor must handle wording, not one fixed layout.
- **Ground truth:** the pricing terms reconcile against **existing** columns —
  `carriers.base_rate`, `carriers.per_kg_rate`, `carriers.fuel_surcharge_pct` — so the
  recoverability layer proves the parse with **no answer leaked**. The one genuinely new
  fact, the per-carrier `guarantee_days`, exists nowhere else, so it ships as a small
  answer-key column beside `body` on `carrier_policies` and is **withheld** when the
  rate cards are handed to students. The signal itself then reconciles against existing
  `deliveries.days_late` + `shipments.shipping_cost` once the thresholds are parsed.
- **Tables:** `carrier_policies.body` (+ withheld `carrier_policies.guarantee_days`),
  `carriers.base_rate`, `carriers.per_kg_rate`, `carriers.fuel_surcharge_pct`,
  `carriers.reliability`, `deliveries.days_late`, `deliveries.status`,
  `shipments.shipping_cost`, `shipments.carrier_id` (join on `shipment_id` / `carrier_id`).
- **Magnitude:** **to be planted.** Candidate thresholds by reliability rank — Summit 1d,
  Pony 1d, BlueDart 2d, Meridian 2d, Coyote 3d — give (measured `seed=7, scale=1.0`,
  full refund of `shipping_cost` on delivered parcels with `days_late ≥ N`):

  | carrier | reliability | guarantee `N` | refund ÷ revenue |
  |---|---|---|---|
  | Summit Courier | 0.97 | 1d | ≈ 0.094 |
  | Pony Express Freight | 0.95 | 1d | ≈ 0.116 |
  | BlueDart Logistics | 0.92 | 2d | ≈ 0.107 |
  | Meridian Parcel | 0.89 | 2d | ≈ 0.133 |
  | Coyote Ground | 0.85 | 3d | ≈ 0.094 |

  The refund-to-revenue ranking (Meridian highest, Summit/Coyote lowest) is **decoupled**
  from the reliability ranking. The counterfactual anchors it: under a **uniform** 2-day
  guarantee for every carrier, refund-to-revenue instead descends monotonically with
  reliability (Coyote highest at ≈ 0.166, Summit lowest at ≈ 0.077) — the ordinary "worst
  carrier owes the most" story. The divergence is produced *entirely* by the per-carrier
  thresholds that live only in the prose. The realiser finalizes the thresholds and
  re-measures at the canonical scale.

An analyst hands each rate card to a parser, pulls the guarantee threshold `N` per
carrier, then applies it to that carrier's delivered parcels: a parcel owes a refund of
its full `shipping_cost` when `days_late ≥ N`. Summed per carrier and divided by that
carrier's shipping revenue, refund exposure is a *policy-shaped* liability, not a
reliability-shaped one. The teaching point is that a rule buried in prose reshapes an
outcome you thought you already had in columns: `deliveries.days_late` alone tells you
who is late, but it cannot tell you who *pays* for being late until the per-carrier
guarantee is read out of the rate card. It pairs with `on-time-degrades-with-zone.md`
(where lateness comes from) and `shipping-cost-right-skew.md` (why the refunded dollars
are cost-weighted): lateness and cost are both in columns, but the guarantee that turns
them into money owed is only in the document. The refund is a downstream teaching
derivation — like the dimensional-weight and fuel-surcharge levers, it is **not** folded
into `shipping_cost`, which stays the clean weight-based identity.

## How to find it

```python
# (1) EXTRACT — parse each rate card's body into structured terms.
import re, polars as pl

def parse_card(body: str) -> dict[str, float | int]:
    # guarantee threshold: the integer of days in the guarantee/refund clause
    n = re.search(r"(\d+)\s*(?:\+|or more)?\s*day", body, re.I)
    base = re.search(r"\$?(\d+\.\d{2})\s*(?:base|per shipment|/shipment)", body, re.I)
    perkg = re.search(r"\$?(\d+\.\d{2})\s*(?:/kg|per kg|per kilogram)", body, re.I)
    fuel = re.search(r"(\d+(?:\.\d)?)\s*%", body)
    return {
        "guarantee_days": int(n.group(1)),
        "base_rate": float(base.group(1)),
        "per_kg_rate": float(perkg.group(1)),
        "fuel_surcharge_pct": float(fuel.group(1)) / 100.0,
    }

# (a) Recoverability, no leak: the parsed pricing terms equal the carriers columns
#     (base_rate / per_kg_rate / fuel_surcharge_pct), and the parsed guarantee_days
#     equals the withheld carrier_policies.guarantee_days answer key.

# (2) AGGREGATE — apply each parsed threshold to that carrier's delivered parcels.
policy = carrier_policies.select("carrier_id", "guarantee_days")   # guarantee_days from parse_card(body)
exposure = (
    deliveries.filter(pl.col("status") == "delivered")
    .join(shipments.select("shipment_id", "carrier_id", "shipping_cost"), on="shipment_id")
    .join(policy, on="carrier_id")
    .join(carriers.select("carrier_id", "reliability"), on="carrier_id")
    .group_by("carrier_id", "reliability")
    .agg(
        pl.col("shipping_cost").filter(pl.col("days_late") >= pl.col("guarantee_days")).sum().alias("refund"),
        pl.col("shipping_cost").sum().alias("revenue"),
    )
    .with_columns((pl.col("refund") / pl.col("revenue")).alias("refund_to_rev"))
    .sort("reliability", descending=True)
)
# refund_to_rev does NOT descend with reliability: highest is a mid-reliability carrier
# (Meridian ≈ 0.13), while the best- and worst-reliability carriers sit lowest (≈ 0.09).
# Under a single uniform threshold it WOULD descend with reliability — the divergence is
# the signal, and it is unreachable without parsing each guarantee from the prose.
```
