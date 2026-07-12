"""The ``rental_receipts`` table: one free-form PVOD rental receipt per rental.

Each row renders a single rental (``rentals``) as an unstructured markdown receipt in
a ``body`` column — the collection's one document-based scenario. The receipt shows the
pre-tax **subtotal** (which reconciles exactly against the real ``rentals.price`` list
column, so nothing is leaked), a per-market **consumption tax** (VAT/GST), and the
**tax-inclusive total charged**. The tax line and the total exist *only* in the prose:
the warehouse stores just the flat USD list ``price``, and the per-region VAT schedule
(``RENTAL_VAT_RATES``) is a withheld answer key — a code constant, not a queryable
column — so the amount a customer actually paid can only be recovered by parsing the
receipt. See ``scenarios/receipts-reveal-a-tax-premium.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from potato_tornado.collections.streaming.constants import REGIONS, RENTAL_VAT_RATES
from potato_tornado.core.collection import GenContext

# Number of receipt phrasings; a name-keyed roll picks one per rental so the parser
# must survive real layout variation, not one memorized byte-for-byte template.
_TEMPLATE_COUNT = 3


@dataclass(frozen=True, slots=True)
class _ReceiptFields:
    """The rendered facts for one receipt, bundled so ``_render`` takes one arg."""

    ref: str
    title: str
    genre: str
    date: str
    market: str
    region: str
    subtotal: float
    rate: int
    vat_amount: float
    total: float


def _render(variant: int, r: _ReceiptFields) -> str:
    """Render one receipt in one of ``_TEMPLATE_COUNT`` phrasings.

    The extractable fields (subtotal, VAT rate, total, two-letter market) read the same
    across every variant; only the surrounding layout changes. US receipts (0% tax) carry
    no ``VAT (N%)`` token, so a parser recovers rate 0 from its absence.
    """
    sub = f"${r.subtotal:.2f}"
    vat = f"${r.vat_amount:.2f}"
    tot = f"${r.total:.2f}"
    taxed = r.rate > 0
    if variant == 0:
        lines = [
            f"# Rental receipt — {r.ref}",
            "",
            f"Title: {r.title} ({r.genre})",
            f"Rented: {r.date} · Market: {r.market} ({r.region})",
            "",
            f"Subtotal:        {sub}",
        ]
        if taxed:
            lines.append(f"VAT ({r.rate}%):       {vat}")
        lines.append("--------------------------")
        lines.append(f"Total charged:   {tot}  (USD)")
        return "\n".join(lines)
    if variant == 1:
        tax_clause = f"VAT ({r.rate}%) {vat}" if taxed else "tax $0.00"
        return (
            f"Receipt {r.ref} — thanks for your rental!\n"
            f"{r.title} · rented {r.date}\n"
            f"Billed to {r.market} ({r.region}). "
            f"List price {sub}, {tax_clause} — you paid {tot} USD."
        )
    lines = [
        f"RENTAL CONFIRMATION · {r.ref}",
        f'"{r.title}" rented {r.date} in {r.market} ({r.region})',
        f"  Subtotal: {sub}",
    ]
    if taxed:
        lines.append(f"  VAT ({r.rate}%): {vat}")
    total_line = f"  Total charged: {tot} (billed USD)"
    if not taxed:
        total_line += "   [tax-free market]"
    lines.append(total_line)
    return "\n".join(lines)


def build_rental_receipts(ctx: GenContext) -> pl.DataFrame:
    rentals = ctx.table("rentals")
    n = rentals.height

    subs = ctx.table("subscribers")
    region_by_sub: dict[str, str] = dict(
        zip(subs["subscriber_id"].to_list(), subs["region"].to_list(), strict=True)
    )
    market_name = {code: name for code, name, *_ in REGIONS}

    titles = ctx.table("titles")
    title_name: dict[str, str] = dict(
        zip(titles["title_id"].to_list(), titles["name"].to_list(), strict=True)
    )
    title_genre: dict[str, str] = dict(
        zip(titles["title_id"].to_list(), titles["genre"].to_list(), strict=True)
    )

    rental_ids = rentals["rental_id"].to_list()
    sub_ids = rentals["subscriber_id"].to_list()
    title_ids = rentals["title_id"].to_list()
    prices = rentals["price"].to_list()
    rented = rentals["rented_date"].to_list()

    # A dedicated child stream picks the phrasing per receipt; being name-keyed it does
    # not reorder any draw in the tables this one reads from.
    variant = ctx.rng.child("template").numpy.integers(0, _TEMPLATE_COUNT, size=n)

    bodies: list[str] = []
    for i in range(n):
        region = region_by_sub[sub_ids[i]]
        rate = RENTAL_VAT_RATES[region]
        subtotal = float(prices[i])
        # Derive the tax-inclusive total from the rendered subtotal — never re-sample the
        # price — and back out the VAT amount so subtotal + vat == total exactly on the
        # face of the receipt.
        total = round(subtotal * (1 + rate / 100), 2)
        vat_amount = round(total - subtotal, 2)
        bodies.append(
            _render(
                int(variant[i]),
                _ReceiptFields(
                    ref=rental_ids[i],
                    title=title_name[title_ids[i]],
                    genre=title_genre[title_ids[i]],
                    date=rented[i].isoformat(),
                    market=market_name[region],
                    region=region,
                    subtotal=subtotal,
                    rate=rate,
                    vat_amount=vat_amount,
                    total=total,
                ),
            )
        )

    return pl.DataFrame(
        {
            "receipt_id": [f"RCPT-{i:07d}" for i in range(1, n + 1)],
            "rental_id": rental_ids,
            "body": bodies,
        }
    )
