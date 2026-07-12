# The amount customers actually pay per rental is highest outside the US

- **Signal:** the effective, tax-inclusive amount charged on a premium rental is *not*
  the flat list price stored in `rentals.price`. Non-US markets add a local
  consumption tax (VAT/GST — GB 20% … JP 10%; the US line is tax-free), so the average
  amount a customer *actually pays* per rental runs ~10–20% higher outside the US even
  though the list price is identical in every market. The US — the largest rental
  market by volume and the ARPU leader on subscriptions — is the **cheapest** effective
  rental market, and this is invisible in the warehouse: only the receipts carry the tax
  and the total.
- **Documents:** `rental_receipts.body` — an unstructured PVOD transaction record (a
  markdown rental receipt), one per rental, ≈ `ctx.n(1500)` rows (750 at the
  seed=7/scale=0.5 test config; floor 1). Emitted by `build_rental_receipts` in three
  name-keyed phrasings (an itemized markdown receipt, a one-line prose confirmation, and a
  labelled confirmation block) so the parser must survive layout variation.
- **Parse target:** the **tax-inclusive total charged** and the **VAT line** (rate + amount),
  which appear *only* in the receipt prose — the warehouse stores just the pre-tax list
  `price`, so the amount the customer paid cannot be read off any column. Example receipts
  (two phrasings, USD throughout — the service bills one global USD list price, so only the
  tax rate varies by market):

  ```
  # Rental receipt — RNT-0004821

  Title: Gordon Ramsay's Nightmare in the Bayou (horror)
  Rented: 2024-03-18 · Market: United Kingdom (GB)

  Subtotal:        $6.99
  VAT (20%):       $1.40
  --------------------------
  Total charged:   $8.39  (USD)
  ```

  ```
  Receipt RNT-0009912 — thanks for your rental!
  Beyoncé in Quantum Harbor · rented 2023-11-02
  Billed to United States (US). List price $4.99, tax $0.00 — you paid $4.99 USD.
  ```

  Pull `total_charged`, the `tax_rate` percentage, and the two-letter `market` code from
  each receipt.
- **Ground truth:** the base/subtotal reconciles against the existing `rentals.price`
  column (the receipt *renders* that value — no answer leaked). The per-region tax
  schedule is a **withheld answer key** — a fixed rate map (US 0% · JP 10% · BR 17% ·
  IN 18% · DE 19% · GB 20%), *not* a queryable column — so the tax-inclusive total
  exists nowhere but the receipt prose. Students get the receipts; the rate map is held
  back for scoring.
- **Tables:** `rental_receipts.body` *(to be planted)*, `rentals.price`,
  `rentals.subscriber_id`, `subscribers.region` (the renter's market, joined on
  `subscriber_id`).
- **Magnitude:** *(measured at seed=7, scale=0.5)* mean list price ≈ **$7.93**/rental, flat
  in distribution across every market (price is a per-transaction draw independent of
  region, so per-market sample means wobble ≈ $7.50–$8.56). The planted VAT schedule is US
  **0%** · JP **10%** · BR **17%** · IN **18%** · DE **19%** · GB **20%**, applied as a flat
  multiplier, so within each market the mean **effective charged / mean list = (1 + VAT)
  exactly**: US **×1.00** · JP **×1.10** · BR **×1.17** · IN **×1.18** · DE **×1.19** · GB
  **×1.20**. Mean effective charged by market ≈ US **$8.12** (cheapest) · JP **$8.44** · IN
  **$9.00** · GB **$9.01** · DE **$9.11** · BR **$10.02** — a ~23% spread, US lowest despite
  being the largest rental market (255 of 750 rentals). Overall blended effective ≈ **$8.81**
  vs the **$7.93** list — an ~11% premium invisible to anyone reading only the `price` column.

The warehouse only knows the *list* price; what a customer was actually charged lives
solely on the receipt. An analyst who wants effective revenue — or the answer to "which
market is the most expensive place to rent?" — has to open the documents, parse the
`Total charged` line out of prose that comes in a couple of layouts, recover the renter's
market, and average. The teaching point is twofold: (1) the number that matters (cash
collected) is a *parse-only* field, not a column, so a clean-SQL analyst silently reports
the wrong figure; and (2) the result **inverts the subscription story** — where the US is
the ARPU premium market (`revenue-concentrates-in-the-us.md`), on the rental line its
zero-VAT list price makes it the cheapest effective ticket, and the tax-heavy European and
Indian markets quietly collect the most per rental. It complements, and does not duplicate,
the flat list-price PVOD facts (`premium-rentals-rate-lower.md`, and the skewed price mix in
`realism-guidance.md`): those are about the *list* ladder; this is about the *charged* total
that the list ladder hides.

## How to find it

```python
# (1) Extraction — pull the charged total, VAT rate, and market from each receipt body.
#     Two layouts, so match both. (regex sketch over rental_receipts.body)
import re
TOTAL = re.compile(r"(?:Total charged:\s*|you paid )\$(\d+\.\d{2})")
RATE  = re.compile(r"(?:VAT|GST) \((\d+)%\)")          # absent (=> 0%) on US receipts
MARKET = re.compile(r"\((US|GB|DE|BR|IN|JP)\)")
# subtotal reconciles against rentals.price:
SUBTOTAL = re.compile(r"(?:Subtotal:\s*|List price )\$(\d+\.\d{2})")
# Layer (a): parsed SUBTOTAL == rentals.price for the receipt's rental_id (proves no leak).
# Layer (b): parsed TOTAL == round(SUBTOTAL * (1 + rate/100), 2), rate from the market.
```

```sql
-- (2) Aggregation over the parsed values: effective charged vs. flat list, by market.
--     `parsed` is the extracted (rental_id, market, subtotal, total_charged) relation.
select p.market,
       count(*)                          as rentals,
       avg(p.subtotal)                   as mean_list,    -- ~7.84 in EVERY market (flat)
       avg(p.total_charged)              as mean_effective  -- US ~7.84 ... GB ~9.41
from parsed p
group by p.market
order by mean_effective;    -- US lowest despite being the largest market by volume
-- The US mean_effective == mean_list (0% tax); every other market pays 10-20% more.
```
