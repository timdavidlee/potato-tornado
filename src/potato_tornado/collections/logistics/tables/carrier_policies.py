"""The ``carrier_policies`` table: one rate-card / service-guarantee document per carrier.

Each carrier ships a single free-form **rate card** (``body``) that renders its real
pricing terms — ``base_rate`` / ``per_kg_rate`` / ``fuel_surcharge_pct``, read straight
from the ``carriers`` dim — as prose, alongside an on-time **refund guarantee** whose
threshold ``guarantee_days`` (the days-late that triggers a full refund of the shipping
charge) differs by carrier: tighter for the premium, reliable carriers and looser for the
budget ground carrier. That threshold lives *only* in the prose, so refund liability can't
be computed until the guarantee is parsed; it ships beside ``body`` as a **withheld**
answer-key column (``guarantee_days``) that is dropped when the cards are handed to
students. The pricing terms, by contrast, reconcile against the existing ``carriers``
columns with no answer leaked. See
``scenarios/refund-exposure-tracks-guarantee-not-reliability.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import polars as pl

from potato_tornado.core.collection import GenContext

# Guarantee threshold (days late that triggers a full refund) by reliability rank,
# most→least reliable. The premium, most-reliable carriers guarantee tightly (1 day); the
# budget, least-reliable carrier guarantees loosely (3 days). Those per-carrier thresholds
# decouple refund exposure from reliability — the least reliable carrier sheds most of its
# misses under its own loose 3-day bar. The length pins the fixed 5-carrier catalog (the
# zip below is strict), so a change to the carrier count fails loudly here.
_GUARANTEE_LADDER = (1, 1, 2, 2, 3)


@dataclass(frozen=True, slots=True)
class _PolicyFacts:
    """The structured terms one rate card renders into prose."""

    carrier_name: str
    transport_mode: str
    base_rate: float
    per_kg_rate: float
    fuel_surcharge_pct: float
    guarantee_days: int


def _card_formal(f: _PolicyFacts) -> str:
    return (
        f"**{f.carrier_name} — Rate Card & Service Guarantee.** Charges are billed at a "
        f"**${f.base_rate:.2f} base** plus **${f.per_kg_rate:.2f}/kg** of actual weight; a "
        f"**{f.fuel_surcharge_pct * 100:.1f}% fuel surcharge** is added. "
        f"{f.transport_mode.title()} service. *Guarantee:* shipping fees are refunded only "
        f"when delivery runs **{f.guarantee_days} or more days** behind the promised date."
    )


def _card_paragraph(f: _PolicyFacts) -> str:
    return (
        f"{f.carrier_name} ({f.transport_mode}). Every shipment carries a "
        f"**${f.base_rate:.2f} per shipment** base charge and **${f.per_kg_rate:.2f} per kg** "
        f"of billable weight, with a fuel surcharge of **{f.fuel_surcharge_pct * 100:.1f}%**. "
        f"On-time promise: we refund the full shipping charge whenever a parcel arrives "
        f"**{f.guarantee_days}+ day(s) late** or worse."
    )


def _card_terms(f: _PolicyFacts) -> str:
    return (
        f"Service terms — {f.carrier_name}. Pricing: **${f.base_rate:.2f}/shipment** plus "
        f"**${f.per_kg_rate:.2f} per kilogram**, with **{f.fuel_surcharge_pct * 100:.1f}%** "
        f"added for fuel. Mode: {f.transport_mode}. Refund policy: the shipping charge is "
        f"refunded in full when a delivery arrives at least **{f.guarantee_days} days** past "
        f"its promised date."
    )


_TEMPLATES: tuple[Callable[[_PolicyFacts], str], ...] = (
    _card_formal,
    _card_paragraph,
    _card_terms,
)


def build_carrier_policies(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference set — one policy per carrier (1:1 with the `carriers` dim), not
    # scaled by row count. Pricing terms are rendered from the carriers columns (they
    # reconcile with no leak); the guarantee threshold is the one genuinely new fact and
    # rides beside `body` as the withheld answer key.
    carriers = ctx.table("carriers")
    ranked_ids = carriers.sort("reliability", descending=True)["carrier_id"].to_list()
    guarantee_of = dict(zip(ranked_ids, _GUARANTEE_LADDER, strict=True))

    # One template per carrier off a name-keyed stream, so the corpus isn't a single fixed
    # layout — a parser must handle the wording, not memorize bytes.
    pick = ctx.rng.child("template").numpy.integers(0, len(_TEMPLATES), size=carriers.height)

    carrier_ids = carriers["carrier_id"].to_list()
    names = carriers["carrier_name"].to_list()
    modes = carriers["transport_mode"].to_list()
    bases = carriers["base_rate"].to_list()
    per_kgs = carriers["per_kg_rate"].to_list()
    fuels = carriers["fuel_surcharge_pct"].to_list()

    bodies: list[str] = []
    guarantees: list[int] = []
    for i, cid in enumerate(carrier_ids):
        n_days = guarantee_of[cid]
        facts = _PolicyFacts(
            carrier_name=names[i],
            transport_mode=modes[i],
            base_rate=bases[i],
            per_kg_rate=per_kgs[i],
            fuel_surcharge_pct=fuels[i],
            guarantee_days=n_days,
        )
        bodies.append(_TEMPLATES[int(pick[i])](facts))
        guarantees.append(n_days)

    return pl.DataFrame(
        {
            "policy_id": [f"POL-{i:02d}" for i in range(1, len(carrier_ids) + 1)],
            "carrier_id": carrier_ids,
            "guarantee_days": guarantees,
            "body": bodies,
        }
    )
